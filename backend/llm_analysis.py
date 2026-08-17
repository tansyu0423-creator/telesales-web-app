import json
from typing import List, Dict, Any
import httpx
from groq import Groq
from google import genai
from google.genai import types

try:
    from .config import settings
    from . import schemas
except ImportError:
    from config import settings
    import schemas

client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
MODEL_NAME = "llama-3.3-70b-versatile"

gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
groq_client = client


def call_openrouter_api(prompt: str) -> Dict[str, Any]:
    """
    OpenRouter API (Mistral等) へフォールバックリクエストを送信する関数。
    """
    api_key = getattr(settings, "openrouter_api_key", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    groq_prompt = prompt + "\n\n出力は必ず以下のキーを持つJSON形式にしてください: {\"purchase_probability\": 0から100の数値, \"customer_interest\": \"文字列\", \"concerns\": \"文字列\", \"recommended_action\": \"文字列\"}"

    payload = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": groq_prompt}],
        "temperature": 0.5,
        "response_format": {"type": "json_object"}
    }
    with httpx.Client(timeout=15.0) as http_client:
        res = http_client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        res.raise_for_status()
        res_data = res.json()
        content = res_data["choices"][0]["message"]["content"]
        return json.loads(content)


def calculate_overlap(start1: float, end1: float, start2: float, end2: float) -> float:
    """2つのタイムセグメントの重なり時間（秒）を計算"""
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    return max(0.0, overlap_end - overlap_start)


def merge_whisper_and_diarization(words, diarization_segments):
    """
    Groq Whisperの単語とPyannoteの話者分離を高精度に同期させ、
    短い相槌や境界線の巻き込みを防ぐ最終チューニング版
    """
    if not words:
        return []

    word_items = []
    for w in words:
        if isinstance(w, dict):
            w_text = str(w.get('word', w.get('text', '')))
            w_start = float(w.get('start', 0.0))
            w_end = float(w.get('end', 0.0))
        else:
            w_text = str(getattr(w, 'word', getattr(w, 'text', '')))
            w_start = float(getattr(w, 'start', 0.0))
            w_end = float(getattr(w, 'end', 0.0))

        word_mid = (w_start + w_end) / 2.0
        
        matched_speaker = None
        for seg in diarization_segments:
            if seg["start"] <= word_mid <= seg["end"]:
                matched_speaker = str(seg["speaker_id"])
                break
        
        if matched_speaker is None:
            for seg in diarization_segments:
                if seg["start"] - 0.15 <= word_mid <= seg["end"] + 0.15:
                    matched_speaker = str(seg["speaker_id"])
                    break

        if matched_speaker is None and word_items:
            matched_speaker = word_items[-1]["speaker"]
        elif matched_speaker is None:
            matched_speaker = "UNKNOWN"

        word_items.append({
            "word": w_text,
            "start": w_start,
            "end": w_end,
            "speaker": matched_speaker
        })

    raw_segments = []
    if not word_items:
        return []

    cur_speaker = word_items[0]["speaker"]
    cur_start = word_items[0]["start"]
    cur_end = word_items[0]["end"]
    cur_text = word_items[0]["word"]

    for i in range(1, len(word_items)):
        item = word_items[i]
        prev_item = word_items[i-1]
        
        speaker_changed = (item["speaker"] != cur_speaker)
        long_pause = (item["start"] - prev_item["end"] > 0.6)
        
        if speaker_changed or long_pause:
            raw_segments.append({
                "speaker": cur_speaker,
                "start": cur_start,
                "end": cur_end,
                "text": cur_text.strip()
            })
            cur_speaker = item["speaker"]
            cur_start = item["start"]
            cur_end = item["end"]
            cur_text = item["word"]
        else:
            cur_text += item["word"]
            cur_end = item["end"]

    if cur_text.strip():
        raw_segments.append({
            "speaker": cur_speaker,
            "start": cur_start,
            "end": cur_end,
            "text": cur_text.strip()
        })

    refined_segments = []
    for seg in raw_segments:
        text = seg["text"]
        start = seg["start"]
        end = seg["end"]
        speaker = seg["speaker"]

        if ("。" in text or "？" in text) and len(text) > 25:
            sentences = [s.strip() for s in text.replace("？", "？\n").replace("。", "。\n").split("\n") if s.strip()]
            if len(sentences) > 1:
                total_len = len(text)
                cur_t = start
                for s in sentences:
                    s_duration = (len(s) / total_len) * (end - start)
                    s_end = cur_t + s_duration
                    refined_segments.append({
                        "speaker": speaker,
                        "start": float(cur_t),
                        "end": float(s_end),
                        "text": s
                    })
                    cur_t = s_end
                continue

        refined_segments.append(seg)

    merged_segments = []
    for seg in refined_segments:
        if not seg["text"]:
            continue
        if merged_segments and merged_segments[-1]["speaker"] == seg["speaker"]:
            if seg["start"] - merged_segments[-1]["end"] < 0.5:
                merged_segments[-1]["text"] += " " + str(seg["text"])
                merged_segments[-1]["end"] = seg["end"]
            else:
                merged_segments.append(seg)
        else:
            merged_segments.append(seg)

    return merged_segments


def merge_consecutive_speakers(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Whisperが認識したテキストのスペースを語尾判定に基づき適切に結合する関数
    """
    if not segments:
        return []

    merged = []

    def format_segment(text: str) -> str:
        parts = [p.strip() for p in text.split() if p.strip()]
        if not parts:
            return ""
        
        formatted_text = ""
        for i, part in enumerate(parts):
            clean_part = part.rstrip("。、！？!?")
            formatted_text += clean_part
            
            if i < len(parts) - 1:
                if clean_part.endswith(("す", "た", "か", "ね", "よ", "さい", "せん", "ましょう", "だ", "ない")):
                    formatted_text += "。"
                else:
                    formatted_text += "、"
        
        if not formatted_text.endswith(("。", "！", "？", "!", "?")):
            formatted_text += "。"
        
        return formatted_text

    first_text = format_segment(segments[0]["text"])
    current = {
        "start": segments[0]["start"],
        "end": segments[0]["end"],
        "text": first_text,
        "speaker": segments[0]["speaker"]
    }

    for next_seg in segments[1:]:
        next_text = format_segment(next_seg["text"])
        if not next_text:
            continue

        if next_seg["speaker"] == current["speaker"]:
            current["end"] = next_seg["end"]
            current["text"] += next_text
        else:
            merged.append(current)
            current = {
                "start": next_seg["start"],
                "end": next_seg["end"],
                "text": next_text,
                "speaker": next_seg["speaker"]
            }
    
    merged.append(current)
    return merged


def identify_roles_by_llm(merged_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """LLMによる発話役割（Sales vs Customer）判定"""
    if not merged_segments:
        return []

    merged_segments.sort(key=lambda x: x["start"])

    dialogue_list = []
    for idx, s in enumerate(merged_segments):
        dialogue_list.append(f"ID:{idx} [Time: {s['start']}s - {s['end']}s]: {s['text']}")
    
    full_sample = "\n".join(dialogue_list)

    prompt = f"""
あなたはプロフェッショナルな音声対話解析AIです。以下のデータは「企業から顧客へかけたアウトバウンドのテレセールス（電話営業）」の文字起こしログです。
各セリフが「営業担当者（Sales）」のものか、「顧客（Customer）」のものかを論理的に判定してください。

【会話ログ】
{full_sample}

【出力形式】
JSON形式で、各セリフのID（文字列の数字）をキー、判定結果（"Sales" または "Customer"）を値にしたオブジェクトのみを出力してください。
"""

    if client:
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            role_map = json.loads(response.choices[0].message.content or "{}")

            final_segments = []
            for idx, s in enumerate(merged_segments):
                text = s["text"].strip()
                assigned_role = role_map.get(str(idx))

                if assigned_role not in ["Sales", "Customer"]:
                    assigned_role = "Sales" if idx == 0 else "Customer"
                
                final_segments.append({
                    "start": s["start"],
                    "end": s["end"],
                    "text": text,
                    "speaker": assigned_role
                })
            
            return merge_consecutive_speakers(final_segments)

        except Exception as e:
            print(f"Role Identification Error: {e}")

    fallback_segments = [
        {
            "start": s["start"],
            "end": s["end"],
            "text": s["text"].strip(),
            "speaker": "Sales" if idx == 0 else "Customer"
        }
        for idx, s in enumerate(merged_segments)
    ]
    return merge_consecutive_speakers(fallback_segments)


import os

def get_rank_thresholds() -> Dict[str, float]:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "system_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                th = data.get("rank_thresholds", {})
                return {
                    "s": float(th.get("s_rank", 90)),
                    "a": float(th.get("a_rank", 70)),
                    "b": float(th.get("b_rank", 50)),
                    "c": float(th.get("c_rank", 30)),
                    "d": float(th.get("d_rank", 10)),
                }
        except Exception:
            pass
    return {"s": 90.0, "a": 70.0, "b": 50.0, "c": 30.0, "d": 10.0}

def derive_rank_from_probability(prob: float) -> str:
    """成約率パーセンテージからランク(S〜E)を自動算出（システム設定の閾値を適用）"""
    try:
        val = float(prob or 0)
    except (ValueError, TypeError):
        val = 0.0

    th = get_rank_thresholds()
    if val >= th["s"]:
        return "S"
    elif val >= th["a"]:
        return "A"
    elif val >= th["b"]:
        return "B"
    elif val >= th["c"]:
        return "C"
    elif val >= th["d"]:
        return "D"
    else:
        return "E"


def analyze_and_score_call(record_id: int, transcripts: List[Dict[str, Any]]) -> schemas.AnalysisResultCreate:
    """
    通話ログを分析し、Gemini -> Groq -> OpenRouter -> デフォルト値 の順でフォールバックしながらスコアリングを実行する。
    """
    if not transcripts:
        return schemas.AnalysisResultCreate(
            call_record_id=record_id,
            rank="C",
            purchase_probability=0,
            customer_interest="対話データなし",
            concerns="対話データなし",
            recommended_action="データがないため評価不能です。"
        )

    dialogue_text = "\n".join([f"{s.get('speaker', 'Unknown')}: {s.get('text', '')}" for s in transcripts])

    prompt = f"""
    あなたはプロのインサイドセールス分析AIです。以下の電話営業の対話ログを細かく評価し、
    顧客の成約意欲・成約率 (`purchase_probability`: 0〜100の数値) を算出してください。

    【数値算出指示 (ルーブリック細密評価)】
    以下の4つの観点（各0〜25点）を個別に厳密に評価し、その合計点（0〜100）を `purchase_probability` としてください。
    1. 顧客の関心・質問の積極性 (0〜25点)
    2. 課題感・導入意欲の深さ (0〜25点)
    3. 次回アクション・スケジュールの具体性 (0〜25点)
    4. 懸念・反論リスクの少なさ (0〜25点)

    【対話ログ】
    {dialogue_text}
    """

    result_dict = {}

    # 1. Primary: Gemini API
    if gemini_client:
        try:
            print("Gemini API でスコアリングを実行中...")
            response = gemini_client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schemas.AnalysisResultBase, 
                    temperature=0.5,
                ),
            )
            
            result_text = response.text or "{}"
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            result_dict = json.loads(result_text.strip())
            
        except Exception as e:
            print(f"Gemini API Error, Groqにフォールバックします: {e}")

    # 2. Secondary: Groq API
    if not result_dict and groq_client:
        try:
            print("Groq API でスコアリングを実行中...")
            groq_prompt = prompt + "\n\n出力は必ず以下のキーを持つJSONにしてください: {\"purchase_probability\": 0から100の数値, \"customer_interest\": \"文字列\", \"concerns\": \"文字列\", \"recommended_action\": \"文字列\"}"
            
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": groq_prompt}],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            result_text = response.choices[0].message.content or "{}"
            result_dict = json.loads(result_text)
        except Exception as e:
            print(f"Groq API Error, OpenRouterにフォールバックします: {e}")

    # 3. Tertiary: OpenRouter API (新規追加)
    if not result_dict and getattr(settings, "openrouter_api_key", ""):
        try:
            print("OpenRouter API でスコアリング（フォールバック）を実行中...")
            result_dict = call_openrouter_api(prompt)
        except Exception as e:
            print(f"OpenRouter API Error: {e}")

    # 4. 安全保護: 全AIサービスダウン・クォータ制限(429)時の安全デフォルト返却
    if not result_dict:
        print("警告: 全てのLLM API（Gemini/Groq/OpenRouter）がクォータ制限またはダウンのため、安全デフォルト値を返却します。")
        return schemas.AnalysisResultCreate(
            call_record_id=record_id,
            rank="C",
            purchase_probability=50,
            customer_interest="API制限のため一時的に解析できません",
            concerns="API制限のため一時的に解析できません",
            recommended_action="APIの利用制限（429）または通信エラーが発生しました。時間を置いて再解析を実行してください。"
        )

    prob = result_dict.get("purchase_probability", 50)
    try:
        prob_val = int(prob)
    except (ValueError, TypeError):
        prob_val = 50

    rank_val = derive_rank_from_probability(prob_val)

    return schemas.AnalysisResultCreate(
        call_record_id=record_id,
        rank=rank_val,
        purchase_probability=prob_val,
        customer_interest=str(result_dict.get("customer_interest", "特になし")),
        concerns=str(result_dict.get("concerns", "特になし")),
        recommended_action=str(result_dict.get("recommended_action", "再コールして状況確認"))
    )
