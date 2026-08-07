import os
from typing import Any
from groq import Groq
from .config import settings

# Groqクライアントの初期化 (.envのキーを自動で読み込みます)
client = Groq(api_key=settings.groq_api_key)

def transcribe_audio(file_path: str) -> Any:
    """
    音声ファイルをGroq Whisper APIに送信し、文字起こし結果を取得する
    """
    try:
        with open(file_path, "rb") as file:
            # APIリクエスト
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(file_path), file.read()),
                model="whisper-large-v3-turbo",
                language="ja",
                response_format="verbose_json",
            )
            return transcription
    except Exception as e:
        print(f"STT Error: {e}")
        raise e