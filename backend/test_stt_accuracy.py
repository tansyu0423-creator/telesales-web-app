import pytest
from unittest.mock import patch, MagicMock
import tempfile
import wave
import os
from backend import stt


def test_transcribe_audio_parameters_and_formatting():
    """STT API呼出時のパラメータ (language='ja', temperature=0.0) およびプロンプトの検証"""
    mock_transcription = MagicMock()
    mock_transcription.words = [
        {"word": "お世話になります", "start": 0.0, "end": 1.2},
        {"word": "よろしくお願いいたします", "start": 1.3, "end": 2.5}
    ]

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        with wave.open(tmp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b'\x00' * 32000)  # 1秒間のダミー音声

    try:
        with patch.object(stt, "client") as mock_client:
            mock_client.audio.transcriptions.create.return_value = mock_transcription

            res = stt.transcribe_audio(tmp_path)

            mock_client.audio.transcriptions.create.assert_called_once()
            call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs

            assert call_kwargs.get("language") == "ja"
            assert call_kwargs.get("temperature") == 0.0
            assert "電話セールス対話" in call_kwargs.get("prompt", "")
            assert res == mock_transcription
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
