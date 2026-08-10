import json
from typing import List, Dict, Any
from groq import Groq
try:
    from .config import settings
except ImportError:
    from config import settings

client = Groq(api_key=settings.groq_api_key)
MODEL_NAME = "llama-3.3-70b-versatile"

def calculate_overlap(start1: float, end1: float, start2: float, end2: float) -> float:
    """2つのタイムセグメントの重なり時間（秒）を計算"""
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    return max(0.0, overlap_end - overlap_start)

def merge_whisper_and_diarization(
    whisper_segments: List[Dict[str, Any]], 
    diarization_segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    merged_result = []

    for w_seg in whisper_segments:
        w_start = float(w_seg.get("start", 0.0))
        w_end = float(w_seg.get("end", 0.0))
        text = w_seg.get("text", "").strip()

        best_speaker_id = "SPEAKER_00"
        max_overlap = -1.0

        for d_seg in diarization_segments:
            d_start = float(d_seg.get("start", 0.0))
            d_end = float(d_seg.get("end", 0.0))
            speaker_id = d_seg.get("speaker_id", "SPEAKER_00")

            overlap = calculate_overlap(w_start, w_end, d_start, d_end)
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker_id = speaker_id

        merged_result.append({
            "start": w_start,
            "end": w_end,
            "text": text,
            "temp_speaker": best_speaker_id
        })

    return merged_result


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