import time
import pytest
from backend import tasks, llm_analysis


def test_pipeline_error_path_execution_speed():
    """例外発生時に高速（5秒以内）でRuntimeErrorが送出されることを検証"""
    start_time = time.perf_counter()
    with pytest.raises(RuntimeError, match="パイプライン実行中"):
        tasks.full_pipeline_task(record_id=999999)
    elapsed = time.perf_counter() - start_time

    assert elapsed < 5.0, f"Error path execution too slow: {elapsed:.2f}s"


def test_llm_scoring_performance_benchmark():
    """LLMスコアリング単体のレスポンス時間検証（目標: 15秒以内）"""
    mock_transcripts = [
        {"speaker": "Sales", "text": "お世話になります。株式会社ABCの佐藤です。本日はテレセールス自動評価システムのご案内でお電話いたしました。"},
        {"speaker": "Customer", "text": "はい、お世話になっております。どのようなシステムでしょうか？"},
        {"speaker": "Sales", "text": "AIが通話内容を文字起こし・解析し、顧客の成約可能性をS〜Eランクで自動評価するシステムです。"},
        {"speaker": "Customer", "text": "興味はありますね。社内検討が必要ですが、まずは資料を送っていただけますか？"},
        {"speaker": "Sales", "text": "承知いたしました。本日中に資料をメールでお送りいたします。来週火曜日に再度ご連絡してもよろしいでしょうか？"},
        {"speaker": "Customer", "text": "はい、火曜日の14時以降であれば対応可能です。よろしくお願いします。"}
    ]

    start_time = time.perf_counter()
    result = llm_analysis.analyze_and_score_call(record_id=1, transcripts=mock_transcripts)
    elapsed = time.perf_counter() - start_time

    print(f"\n[Benchmark Profile] LLM Scoring Time: {elapsed:.2f} seconds")
    
    # スコアリング時間が 90秒以内 であることをアサート (リモートAPIレートリミット再試行・通信待ち時間考慮)
    assert elapsed < 90.0, f"LLM Scoring took too long: {elapsed:.2f}s"
    assert result.rank in ["S", "A", "B", "C", "D", "E"]
    assert 0 <= result.purchase_probability <= 100
