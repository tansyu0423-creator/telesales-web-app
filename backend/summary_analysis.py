import json
from typing import Dict, Any, List
from google import genai
from google.genai import types
from groq import Groq

try:
    from .config import settings
except ImportError:
    from config import settings

gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
groq_client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None

def summarize_call(transcripts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    通話ログを受け取り、要約、購買シグナル、否定的シグナルを抽出する関数。
    Gemini 2.0 Flash を優先し、エラー時は Groq (Llama 3.3 70B) にフォールバックする。
    """
    if not transcripts:
        return {"summary": "トランスクリプトがありません。", "buying_signals": [], "negative_signals": []}

    dialogue_text = "\n".join([f"{s.get('speaker', 'Unknown')}: {s.get('text', '')}" for s in transcripts])

    prompt = f"""
あなたはプロのインサイドセールス分析AIです。以下の電話営業の対話ログを分析し、JSON形式で結果を出力してください。

【対話ログ】
{dialogue_text}

【出力形式（必ず以下のJSONキーを含めること）】
{{
    "summary": "通話全体の要約（200文字程度で簡潔に）",
    "buying_signals": ["顧客の肯定的な反応や、興味を示している点", "価格や導入時期に関する前向きな質問など"],
    "negative_signals": ["顧客が示した懸念点や難色", "時期尚早、価格への不満などのネガティブな反応"]
}}
"""

    if gemini_client:
        try:
            print("Gemini API で分析を実行中...")
            response = gemini_client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            result_text = response.text or "{}"
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            return json.loads(result_text)
        except Exception as e:
            print(f"Gemini API Error, Groqにフォールバックします: {e}")

    if groq_client:
        try:
            print("Groq API で分析を実行中...")
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            result_text = response.choices[0].message.content or "{}"
            return json.loads(result_text)
        except Exception as e:
            print(f"Groq API Error: {e}")

    return {
        "summary": "AI解析中にエラーが発生しました。",
        "buying_signals": [],
        "negative_signals": []
    }
