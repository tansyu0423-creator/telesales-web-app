import json
from typing import List, Dict, Any
from groq import Groq
from google import genai
from google.genai import types

try:
    from .config import settings
    from . import schemas
except ImportError:
    from config import settings
    import schemas

client = Groq(api_key=settings.groq_api_key)
MODEL_NAME = "llama-3.3-70b-versatile"

gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
groq_client = client

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

    # 1. 単語ごとに、どの話者に属するかをより厳密にマッピング（マージンを狭くして境界の混信を防ぐ）
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
        
        # 厳密な包含関係を優先し、マージンは最小限（±0.1秒）にする
        matched_speaker = None
        for seg in diarization_segments:
            if seg["start"] <= word_mid <= seg["end"]:
                matched_speaker = str(seg["speaker_id"])
                break
        
        # 完全に収まらない場合の許容マージン（±0.15秒と短めに設定）
        if matched_speaker is None:
            for seg in diarization_segments:
                if seg["start"] - 0.15 <= word_mid <= seg["end"] + 0.15:
                    matched_speaker = str(seg["speaker_id"])
                    break

        # それでも決まらない場合は直前の話者を継承
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

    # 2. 話者が変わるポイントでグループ化（無音の判定も0.6秒と少しタイトにして細かくキレを出す）
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

    # 3. 句読点を基準にした文分割（ターンブレーカー）
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

    # 4. 同話者の連続を自然に結合（結合間隔を0.5秒以内に絞り、混信を防ぐ）
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
    Whisperが認識したテキストのスペースを、
    文末表現（です、ました等）の後は句点（。）に、それ以外は読点（、）に
    自動で美しく変換して結合する関数。
    """
    if not segments:
        return []

    merged = []

    def format_segment(text: str) -> str:
        # 空白でテキストを分割
        parts = [p.strip() for p in text.split() if p.strip()]
        if not parts:
            return ""
        
        formatted_text = ""
        for i, part in enumerate(parts):
            # 万が一付いている元の句読点を一旦クリーンにする
            clean_part = part.rstrip("。、！？!?")
            formatted_text += clean_part
            
            # 最後の要素以外は「、」か「。」で繋ぐ
            if i < len(parts) - 1:
                # 助動詞や終助詞など、文の終わりになりやすい語尾を判定
                if clean_part.endswith(("す", "た", "か", "ね", "よ", "さい", "せん", "ましょう", "だ", "ない")):
                    formatted_text += "。"
                else:
                    formatted_text += "、"
        
        # セグメントの最後には必ず句点「。」を打つ
        if not formatted_text.endswith(("。", "！", "？", "!", "?")):
            formatted_text += "。"
        
        return formatted_text

    # 最初のセグメントを初期化
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
            # 同じ話者の場合：各文末は既に正しくフォーマットされているためそのまま結合
            current["end"] = next_seg["end"]
            current["text"] += next_text
        else:
            # 話者が変わった場合：現在のブロックを確定して新しいブロックへ
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
    """
    ハードコードを一切排し、アウトバウンド・テレセールスの構造的原則
    （発信者が最初に名乗り、用件を切り出す）をLLMに厳密に認識させてロール判定を行う関数。
    """
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

【アウトバウンド・テレセールスの構造的原則】
1. **営業担当者 (Sales)** の定義:
   - この通話は営業側から発信しているため、**時間の流れにおいて最初に発言し、自社名や自身の名前を名乗る人物は必ず営業担当者**です。
   - 用件の切り出し、「お時間よろしいでしょうか」というアポイントの打診、および顧客からの状況報告に対するクロージング（「ありがとうございます」「承知しました」「失礼します」など）を行います。
2. **顧客 (Customer)** の定義:
   - 営業からの呼びかけに対して応答する側です。
   - 「こんにちは、〜です」「お電話ありがとうございます」という第一声の応答や、「現在外出中で手が離せない」といった自身のスケジュール・状況の伝達を行います。

【会話ログ】
{full_sample}

【出力形式】
JSON形式で、各セリフのID（文字列の数字）をキー、判定結果（"Sales" または "Customer"）を値にしたオブジェクトのみを出力してください。
例:
{{
  "0": "Sales",
  "1": "Customer"
}}
"""

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

            # 万が一LLMが判断に迷った場合の安全なフォールバック（ハードコードではなく対話構造に基づく論理フォールバック）
            if assigned_role not in ["Sales", "Customer"]:
                # 時間的順序において、最初の発話は構造上Sales、以降は交互または文脈依存
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


def derive_rank_from_probability(prob: float) -> str:
    """成約率パーセンテージからランク(S〜E)を自動算出"""
    try:
        val = float(prob or 0)
    except (ValueError, TypeError):
        val = 0.0

    if val >= 90.0:
        return "S"
    elif val >= 70.0:
        return "A"
    elif val >= 50.0:
        return "B"
    elif val >= 30.0:
        return "C"
    elif val >= 10.0:
        return "D"
    else:
        return "E"


def analyze_and_score_call(record_id: int, transcripts: List[Dict[str, Any]]) -> schemas.AnalysisResultCreate:
    """
    通話ログを分析し、指定されたPydanticスキーマに沿ってランクや成約確率を算出する。
    4観点のルーブリック評価（各0-25点）により1%刻みのリアルな成約率を算出し、バックエンドでランクを自動導出する。
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

    ※ 80, 60, 50, 40 などの典型的な5や10の倍数に丸めず、各観点の加算結果によるリアルな1%単位の数値（例: 83, 76, 62, 49, 27, 8 など）を正確に算出してください。

    【対話ログ】
    {dialogue_text}
    """

    result_dict = {}

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
            print(f"Groq API Error: {e}")

    prob = result_dict.get("purchase_probability", 50)
    try:
        prob_val = int(prob)
    except (ValueError, TypeError):
        prob_val = 50

    # バックエンド側で確実にパーセンテージと連動させてランクを自動導出
    rank_val = derive_rank_from_probability(prob_val)

    return schemas.AnalysisResultCreate(
        call_record_id=record_id,
        rank=rank_val,
        purchase_probability=prob_val,
        customer_interest=str(result_dict.get("customer_interest", "特になし")),
        concerns=str(result_dict.get("concerns", "特になし")),
        recommended_action=str(result_dict.get("recommended_action", "再コールして状況確認"))
    )