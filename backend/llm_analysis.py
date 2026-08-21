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

GROQ_TIMEOUT_SECONDS = 2.0
MODEL_NAME = settings.groq_model
client = Groq(api_key=settings.groq_api_key, timeout=GROQ_TIMEOUT_SECONDS) if settings.groq_api_key else None

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
    groq_prompt = prompt + "\n\n【重要】出力はJSONのみ。purchase_probability と rank は出力せず、interest_score、need_score、action_score、risk_score（各0〜25の1点単位の整数）、customer_interest、concerns、recommended_actionを返してください。文章は必ず日本語にしてください。"

    payload = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": groq_prompt}],
        "temperature": 0.1,
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
    対話の構造的ターン交替（Turn-Taking）に基づき、同じ話者（Sales / Customer）の
    連続発話を相手話者の切り替わりが発生するまで単一の対話ターンとして結合する汎用設計
    """
    if not segments:
        return []

    merged = []

    def format_segment(text: str) -> str:
        if not text:
            return ""
        t = text.strip()
        if t and not t.endswith(("。", "！", "？", "!", "?", "…")):
            t += "。"
        return t

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

        # 話者が同じである限り、相手話者の発言が入るまで1つの対話ターンとして結合
        if next_seg["speaker"] == current["speaker"]:
            current["end"] = next_seg["end"]
            current["text"] += (" " if not current["text"].endswith(("。", "！", "？", "!", "?")) else "") + next_text
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
    """Pyannoteの話者ID（SPEAKER_00, SPEAKER_01等）を、LLMを用いてSalesとCustomerに紐付ける"""
    if not merged_segments:
        return []

    merged_segments.sort(key=lambda x: x["start"])

    # 登場するユニークな話者IDを取得
    speakers = list(dict.fromkeys([s["speaker"] for s in merged_segments if s.get("speaker")]))

    # すでに Sales / Customer に分類されている場合はそのまま校正のみ
    if set(speakers).issubset({"Sales", "Customer"}):
        return proofread_transcripts_with_llm(merged_segments)

    # 話者IDの対応関係を決定
    speaker_map = {}
    if len(speakers) >= 2:
        sample_dialogue = []
        for s in merged_segments[:8]:
            sample_dialogue.append(f"{s['speaker']}: {s['text']}")

        prompt = f"""
以下の対話ログはアウトバウンドの電話営業（テレアポ）の冒頭部分です。
{chr(10).join(sample_dialogue)}

話者ID（{', '.join(speakers)}）のうち、どちらが営業担当者（Sales）で、どちらが顧客（Customer）かを判定し、以下のJSON形式のみで答えてください。
例: {{"{speakers[0]}": "Sales", "{speakers[1]}": "Customer"}}
"""
        if client:
            try:
                res = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                speaker_map = json.loads(res.choices[0].message.content or "{}")
            except Exception as e:
                print(f"Role Speaker Map Error: {e}")

    # デフォルトのフォールバックマッピング
    first_speaker = merged_segments[0]["speaker"]
    for spk in speakers:
        if spk not in speaker_map:
            speaker_map[spk] = "Sales" if spk == first_speaker else "Customer"

    final_segments = []
    for s in merged_segments:
        spk = s["speaker"]
        role = speaker_map.get(spk, "Sales" if spk == first_speaker else "Customer")
        final_segments.append({
            "start": s["start"],
            "end": s["end"],
            "text": s["text"].strip(),
            "speaker": role
        })

    merged_result = merge_consecutive_speakers(final_segments)
    return proofread_transcripts_with_llm(merged_result)


def proofread_transcripts_with_llm(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    特定の音声ファイルに依存するハードコード文字置換を行わず、
    LLM（Gemini / Groq）が対話全体の前後文脈を汎用的に解析し、
    話者の誤判定修復およびSTT特有の誤認識（語頭の欠落・同音異義語・誤漢字・途切れた文末）を全自動で校正・補正する汎用恒久処理
    """
    if not segments:
        return segments

    dialogue_lines = [f"[{i}] {s.get('speaker', 'Unknown')}: {s.get('text', '')}" for i, s in enumerate(segments)]
    full_text = "\n".join(dialogue_lines)

    prompt = f"""
あなたはプロの日本語音声対話AI校正スペシャリストです。
以下は電話営業（テレアポ）の音声認識（STT）および話者分離によって得られた会話ログです。

【校正方針（汎用・自律修正）】
1. **口語・発音の崩れ・言い淀み・語頭語尾切断の標準語整形**: 音声認識によって『こんちょっと』『こん』等の発音崩れや言い淀み・誤記として取得された不自然な表現を、会話全体の前後文脈から推測して標準的で読みやすい綺麗な日本語表現（『今ちょっと』等）に確実に校正・修正してください。
2. **誤字・同音異義語の校正**: 専門用語や音素誤認識（例: 『生態情報』➔『生体情報』、『終時』➔『週次』、『機械損失』➔『機会損失』）を正しい用語に校正してください。
3. **会話の流れと整合性の維持**: 話者（Sales/Customer）、発話順、発話数は変更せず、テキストだけを校正してください。
4. **文脈に基づく分断修復**: 話者切り替えやSTTの単語分割で文が不自然に分断されている場合は、前後の文脈から自然な日本語へ修復してください。特定の単語・フレーズ・話者を根拠にした固定ルールは使わないでください。
5. **【要約・文節削除の絶対禁止】**: 入力テキストに含まれるすべての文章・節をスキップ・短縮・要約せず、全文を保持してください。
6. **出力形式**: 出力はJSONオブジェクトのみとし、キーにセリフのインデックス文字列（"0", "1", "2"...）、値に校正後の発話テキストを指定してください。

【会話ログ】
{full_text}
"""
    proofread_map = {}
    if gemini_client:
        try:
            response = gemini_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            res_text = response.text or "{}"
            if res_text.startswith("```json"):
                res_text = res_text[7:]
            if res_text.startswith("```"):
                res_text = res_text[3:]
            if res_text.endswith("```"):
                res_text = res_text[:-3]
            proofread_map = json.loads(res_text.strip())
        except Exception as e:
            print(f"LLM Proofread Gemini Error: {e}")

    if not proofread_map and groq_client:
        try:
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a Japanese text proofreader. Output valid JSON mapping index string to text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4096,
                response_format={"type": "json_object"}
            )
            proofread_map = json.loads(response.choices[0].message.content or "{}")
        except Exception as e:
            print(f"LLM Proofread Groq Error: {e}")

    if proofread_map:
        for idx, s in enumerate(segments):
            corrected = proofread_map.get(str(idx)) or proofread_map.get(idx)
            if corrected and isinstance(corrected, str) and corrected.strip():
                clean_text = corrected.strip()
                for prefix in ["Sales:", "Customer:", "Sales：", "Customer：", f"{s.get('speaker', '')}:", f"{s.get('speaker', '')}："]:
                    if clean_text.startswith(prefix):
                        clean_text = clean_text[len(prefix):].strip()
                s["text"] = clean_text

    return segments


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
    顧客の成約意欲を4項目で採点してください。成約率はアプリケーション側で算出します。

    【言語指定（最優先指示）】
    ・出力するすべての文章（`customer_interest`, `concerns`, `recommended_action`）は【必ず日本語】で記述してください。英語は絶対に使用しないでください。

    【数値算出指示 (ルーブリック細密評価)】
    以下の4つの観点を、対話中の具体的な発言を根拠に1点単位で個別採点してください。
    各項目は0〜25点の整数とし、5点刻みに固定せず、会話の根拠に応じて1点単位で採点してください。
    成約率はあなたが直接決めず、アプリ側で4項目を合計して算出します。
    ランク閾値や過去の例の数値を採点根拠にせず、対話内容から毎回独立して評価してください。
    1. `interest_score`: 顧客の関心・質問の積極性 (0〜25点)
    2. `need_score`: 課題感・導入意欲の深さ (0〜25点)
    3. `action_score`: 次回アクション・スケジュールの具体性 (0〜25点)
    4. `risk_score`: 懸念・反論リスクの少なさ (0〜25点)

    【評価例 (Few-shot 判定サンプル)】
    ・例1 (Sランク・非常に有望):
      対話: 顧客「ぜひ導入したいです。来週月曜日に契約書を送ってください。」
      期待評価: 関心・課題感・次回アクションがすべて確定し懸念なし。
    採点例: interest_score=24, need_score=23, action_score=23, risk_score=22

    ・例2 (Bランク・検討中):
      対話: 顧客「興味はありますが、予算と社内検討が必要です。資料をいただけますか。」
      期待評価: 関心はあるが他社比較や予算調整が必要。
    採点例: interest_score=18, need_score=15, action_score=14, risk_score=15

    ・例3 (Eランク・不可行):
      対話: 顧客「すでに他社製品を長期契約したばかりで全く必要ありません。結構です。」
      期待評価: 明確な拒絶・ターゲット外。
            採点例: interest_score=2, need_score=1, action_score=0, risk_score=2

        【出力形式】
        rank と purchase_probability は出力せず、以下のキーを持つJSONのみを返してください。
        interest_score, need_score, action_score, risk_score, customer_interest, concerns, recommended_action

    【対話ログ】
    {dialogue_text}
    """

    result_dict = {}

    # 1. Primary: Gemini API
    if gemini_client:
        try:
            print("Gemini API でスコアリングを実行中...")
            response = gemini_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schemas.AnalysisScoreResponse,
                    temperature=0.1,
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
            groq_prompt = prompt + "\n\n【重要】出力はJSONのみ。purchase_probability と rank は出力せず、interest_score、need_score、action_score、risk_score（各0〜25の1点単位の整数）、customer_interest、concerns、recommended_actionを返してください。文章は必ず日本語にしてください。"
            
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": groq_prompt}],
                temperature=0.1,
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

    score_keys = ("interest_score", "need_score", "action_score", "risk_score")
    if all(key in result_dict for key in score_keys):
        try:
            clamped_scores = [max(0, min(25, int(result_dict[key]))) for key in score_keys]
            prob = sum(clamped_scores)
        except (TypeError, ValueError):
            prob = 50
    else:
        prob = result_dict.get("purchase_probability", 50)
    try:
        prob_val = max(0, min(100, int(prob)))
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
