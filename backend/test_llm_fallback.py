import pytest
from unittest.mock import patch, MagicMock
from backend import llm_analysis, schemas


def test_analyze_and_score_call_gemini_success():
    """1. Gemini APIが正常動作する場合のテスト"""
    mock_transcripts = [
        {"speaker": "Sales", "text": "お世話になります。株式会社サンプルです。"},
        {"speaker": "Customer", "text": "ぜひ契約を進めたいです。"}
    ]
    mock_gemini_response = MagicMock()
    mock_gemini_response.text = '{"purchase_probability": 95, "customer_interest": "高い", "concerns": "特になし", "recommended_action": "契約書送付"}'

    with patch.object(llm_analysis, "gemini_client") as mock_gemini:
        mock_gemini.models.generate_content.return_value = mock_gemini_response
        result = llm_analysis.analyze_and_score_call(record_id=1, transcripts=mock_transcripts)
        
        assert isinstance(result, schemas.AnalysisResultCreate)
        assert result.rank == "S"
        assert result.purchase_probability == 95
        assert result.customer_interest == "高い"


def test_analyze_and_score_call_groq_fallback():
    """2. Geminiエラー(429)時にGroqへ正しくフォールバックするかのテスト"""
    mock_transcripts = [{"speaker": "Sales", "text": "お世話になります。"}, {"speaker": "Customer", "text": "検討中です。"}]
    mock_groq_response = MagicMock()
    mock_groq_response.choices = [
        MagicMock(message=MagicMock(content='{"purchase_probability": 60, "customer_interest": "普通", "concerns": "価格", "recommended_action": "見積再送"}'))
    ]

    with patch.object(llm_analysis, "gemini_client") as mock_gemini, \
         patch.object(llm_analysis, "groq_client") as mock_groq:
        mock_gemini.models.generate_content.side_effect = Exception("429 RateLimit Exceeded")
        mock_groq.chat.completions.create.return_value = mock_groq_response

        result = llm_analysis.analyze_and_score_call(record_id=1, transcripts=mock_transcripts)
        assert isinstance(result, schemas.AnalysisResultCreate)
        assert result.rank == "B"
        assert result.purchase_probability == 60


def test_analyze_and_score_call_openrouter_fallback():
    """3. Gemini/Groq障害時にOpenRouterへフォールバックするかのテスト"""
    mock_transcripts = [{"speaker": "Sales", "text": "こんにちは。"}, {"speaker": "Customer", "text": "興味があります。"}]
    mock_openrouter_data = {
        "purchase_probability": 75,
        "customer_interest": "高い",
        "concerns": "納期",
        "recommended_action": "資料送付"
    }

    with patch.object(llm_analysis, "gemini_client") as mock_gemini, \
         patch.object(llm_analysis, "groq_client") as mock_groq, \
         patch.object(llm_analysis.settings, "openrouter_api_key", "dummy_key"), \
         patch.object(llm_analysis, "call_openrouter_api") as mock_openrouter:
        mock_gemini.models.generate_content.side_effect = Exception("Gemini Error")
        mock_groq.chat.completions.create.side_effect = Exception("Groq Error")
        mock_openrouter.return_value = mock_openrouter_data

        result = llm_analysis.analyze_and_score_call(record_id=1, transcripts=mock_transcripts)

        assert isinstance(result, schemas.AnalysisResultCreate)
        assert result.rank == "A"
        assert result.purchase_probability == 75


def test_analyze_and_score_call_all_ai_down_safe_default():
    """4. 全AIサービスダウン・クォータ枯渇時に安全なデフォルト結果が返るかのテスト"""
    mock_transcripts = [{"speaker": "Sales", "text": "こんにちは。"}, {"speaker": "Customer", "text": "はい。"}]

    with patch.object(llm_analysis, "gemini_client") as mock_gemini, \
         patch.object(llm_analysis, "groq_client") as mock_groq, \
         patch.object(llm_analysis.settings, "openrouter_api_key", ""):
        mock_gemini.models.generate_content.side_effect = Exception("429 Quota Error")
        mock_groq.chat.completions.create.side_effect = Exception("Groq Service Error")

        result = llm_analysis.analyze_and_score_call(record_id=1, transcripts=mock_transcripts)

        assert isinstance(result, schemas.AnalysisResultCreate)
        assert result.rank == "C"
        assert result.purchase_probability == 50
        assert "一時的に解析できません" in result.customer_interest
