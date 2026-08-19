import pytest
from backend import tasks


def test_full_pipeline_task_error_handling():
    """存在しないレコードIDはCeleryのFAILUREへ伝播する"""
    with pytest.raises(RuntimeError, match="パイプライン実行中"):
        tasks.full_pipeline_task(record_id=999999)


def test_transcribe_task_corrupted_file_error_handling():
    """存在しないレコードIDはCeleryのFAILUREへ伝播する"""
    with pytest.raises(RuntimeError, match="文字起こし・話者分離処理"):
        tasks.transcribe_and_diarize_task(record_id=999999)


