import os
import sys
import pytest
import io
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import app
except ImportError:
    from backend.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_create_and_read_call_record():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "sales_code": "SALES_999",
            "customer_phone": "080-9999-8888",
            "call_duration": 300,
            "audio_file_path": "audio-123.wav"
        }
        post_resp = await ac.post("/records/", json=payload)
        assert post_resp.status_code == 200
        data = post_resp.json()
        assert data["sales_code"] == "SALES_999"
        assert data["customer_phone"] == "080-9999-8888"
        assert "id" in data

        record_id = data["id"]
        get_resp = await ac.get(f"/records/{record_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == record_id

@pytest.mark.asyncio
async def test_read_records_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/records/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_upload_audio():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        fake_wav = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00")
        files = {"file": ("test_call.wav", fake_wav, "audio/wav")}
        response = await ac.post("/upload/", files=files)
        assert response.status_code == 200
        res_data = response.json()
        assert "saved_filename" in res_data
        assert res_data["original_filename"] == "test_call.wav"

@pytest.mark.asyncio
async def test_analyze_and_export_csv():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. テスト用通話レコードの作成
        payload = {
            "sales_code": "REP_TEST",
            "customer_phone": "090-0000-1111",
            "call_duration": 150,
            "audio_file_path": "sample.wav"
        }
        post_resp = await ac.post("/records/", json=payload)
        record_id = post_resp.json()["id"]
        # 2. LLM役割同定のモックテスト
        mock_roles = [
            {"start": 0.0, "end": 5.0, "text": "こんにちは", "speaker": "Sales"}
        ]
        with patch("main.llm_analysis.identify_roles_by_llm", return_value=mock_roles):
            pass
        csv_resp = await ac.get(f"/records/{record_id}/export/csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers.get("content-type", "")
        assert "REP_TEST" in csv_resp.text

@pytest.mark.asyncio
async def test_merge_and_role_identification():
    from llm_analysis import merge_whisper_and_diarization
    whisper_segs = [
        {"start": 0.0, "end": 4.0, "text": "お世話になります。サービスのご案内です。"},
        {"start": 4.5, "end": 9.0, "text": "はい、詳しく聞かせてください。"}
    ]
    diarization_segs = [
        {"start": 0.0, "end": 4.2, "speaker_id": "SPEAKER_00"},
        {"start": 4.3, "end": 9.5, "speaker_id": "SPEAKER_01"}
    ]
    merged = merge_whisper_and_diarization(whisper_segs, diarization_segs)
    assert len(merged) == 2
    assert merged[0]["temp_speaker"] == "SPEAKER_00"
    assert merged[1]["temp_speaker"] == "SPEAKER_01"

@pytest.mark.asyncio
async def test_summarize_api_no_transcript():
    """トランスクリプト（文字起こし）がない状態で要約APIを呼ぶと、正しく400エラーで弾かれるかのテスト"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "sales_code": "SUM_TEST_01",
            "customer_phone": "090-8888-7777",
            "call_duration": 120,
            "audio_file_path": "summary_test.wav"
        }
        post_resp = await ac.post("/records/", json=payload)
        record_id = post_resp.json()["id"]

        sum_resp = await ac.post(f"/records/{record_id}/summarize")
        
        assert sum_resp.status_code == 400
        assert "文字起こしデータが存在しません" in sum_resp.json()["detail"]


@patch("summary_analysis.gemini_client")
def test_summarize_call_module(mock_gemini):
    """AI要約モジュール (summary_analysis) が正しくデータをパース（解析）するかの単体テスト"""
    from summary_analysis import summarize_call
    
    empty_result = summarize_call([])
    assert "トランスクリプトがありません" in empty_result["summary"]
    
    class MockResponse:
        text = '{"summary": "モックされた要約テストです", "buying_signals": ["価格に興味あり"], "negative_signals": []}'
        
    mock_gemini.models.generate_content.return_value = MockResponse()
    
    sample_transcripts = [
        {"speaker": "Sales", "text": "本日はよろしくお願いいたします。"},
        {"speaker": "Customer", "text": "よろしくお願いします。"}
    ]
    
    result = summarize_call(sample_transcripts)
    
    assert result["summary"] == "モックされた要約テストです"
    assert "価格に興味あり" in result["buying_signals"]
    assert len(result["negative_signals"]) == 0