import os
import sys
import pytest
import io
from httpx import AsyncClient, ASGITransport

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
