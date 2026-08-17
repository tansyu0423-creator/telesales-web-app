import pytest
from backend import tasks


def test_full_pipeline_task_error_handling():
    """存在しないレコードIDまたはDB未接続時のエラー捕獲テスト (status: failure)"""
    res = tasks.full_pipeline_task(record_id=999999)
    assert isinstance(res, dict)
    assert res.get("status") == "failure"
    assert "error" in res


def test_transcribe_task_corrupted_file_error_handling():
    """文字起こしタスクにおけるエラー捕獲テスト (status: failure)"""
    res = tasks.transcribe_and_diarize_task(record_id=999999)
    assert isinstance(res, dict)
    assert res.get("status") == "failure"
    assert "error" in res


