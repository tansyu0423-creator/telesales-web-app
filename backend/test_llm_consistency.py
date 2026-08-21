import pytest
from unittest.mock import patch, MagicMock
from backend import llm_analysis, schemas


def test_analyze_and_score_call_few_shot_prompt_formatting():
    """Gemini/Groq のプロンプトに Few-shot サンプルが含まれているか、temperatureが0.1に設定されているかの検証"""
    mock_transcripts = [
        {"speaker": "Sales", "text": "お世話になります。サービスのご案内です。"},
        {"speaker": "Customer", "text": "興味がありますが社内検討が必要です。"}
    ]

    mock_gemini_response = MagicMock()
    mock_gemini_response.text = '{"interest_score": 18, "need_score": 15, "action_score": 14, "risk_score": 15, "customer_interest": "高い", "concerns": "社内承認", "recommended_action": "資料送付"}'

    with patch.object(llm_analysis, "gemini_client") as mock_gemini:
        mock_gemini.models.generate_content.return_value = mock_gemini_response

        result = llm_analysis.analyze_and_score_call(record_id=1, transcripts=mock_transcripts)

        mock_gemini.models.generate_content.assert_called_once()
        call_kwargs = mock_gemini.models.generate_content.call_args.kwargs
        contents_prompt = call_kwargs.get("contents", "")
        config = call_kwargs.get("config")

        # Few-shot サンプルが含まれているか確認
        assert "Few-shot 判定サンプル" in contents_prompt
        assert "Sランク・非常に有望" in contents_prompt
        assert "Bランク・検討中" in contents_prompt
        assert "Eランク・不可行" in contents_prompt

        # temperature が 0.1 に設定されているか確認
        assert config.temperature == 0.1

        assert isinstance(result, schemas.AnalysisResultCreate)
        assert result.rank == "B"
        assert result.purchase_probability == 62


def test_llm_consistency_reproducibility_mock():
    """同一ログに対して複数回スコアリングを呼び出した場合の判定の安定性と整合性を検証"""
    mock_transcripts = [
        {"speaker": "Sales", "text": "こんにちは、ABCシステムです。"},
        {"speaker": "Customer", "text": "ぜひ契約を進めたいです。"}
    ]
    mock_gemini_response = MagicMock()
    mock_gemini_response.text = '{"interest_score": 24, "need_score": 23, "action_score": 23, "risk_score": 22, "customer_interest": "非常に高い", "concerns": "なし", "recommended_action": "契約書送付"}'

    with patch.object(llm_analysis, "gemini_client") as mock_gemini:
        mock_gemini.models.generate_content.return_value = mock_gemini_response

        results = [
            llm_analysis.analyze_and_score_call(record_id=1, transcripts=mock_transcripts)
            for _ in range(3)
        ]

        # 3回の実行結果がすべて同一のランクとパーセンテージであることを確認
        assert all(r.rank == "S" for r in results)
        assert all(r.purchase_probability == 92 for r in results)


def test_proofreader_does_not_change_speaker_for_fixed_phrases():
    """校正処理は固定フレーズを根拠に話者を変更しない"""
    segments = [
        {
            "speaker": "Customer",
            "start": 0.0,
            "end": 1.0,
            "text": "ご案内を受けました。"
        }
    ]

    with patch.object(llm_analysis, "gemini_client", None), patch.object(llm_analysis, "groq_client", None):
        proofread = llm_analysis.proofread_transcripts_with_llm(segments)

    assert proofread[0]["speaker"] == "Customer"

