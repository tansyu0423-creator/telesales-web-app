import os
import wave
import tempfile
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def transcribe_audio(file_path: str):
    """
    Groq APIを利用して文字起こしを実行する。
    25MBのファイルサイズ制限を回避するため、長時間の音声は自動的に10分ごとに分割処理する。
    """
    CHUNK_LENGTH_SEC = 600  # 10分 (16kHz WAVなら約19MBで安全圏)
    
    with wave.open(file_path, 'rb') as wf:
        framerate = wf.getframerate()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        total_duration = n_frames / float(framerate)
        
    # 10分以下の短いファイルの場合はそのまま処理
    if total_duration <= CHUNK_LENGTH_SEC:
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(file_path), file.read()),
                model="whisper-large-v3-turbo",  # モデル名は必要に応じて変更可
                prompt="営業と顧客の会話です。日本語で出力してください。",
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
        return transcription

    # 10分を超える場合はチャンク分割処理
    print(f"Audio duration ({total_duration:.1f}s) exceeds limit. Splitting into chunks...")
    all_words = []
    current_frame = 0
    frames_per_chunk = CHUNK_LENGTH_SEC * framerate
    chunk_index = 0
    
    with wave.open(file_path, 'rb') as wf:
        while current_frame < n_frames:
            frames_to_read = min(frames_per_chunk, n_frames - current_frame)
            chunk_data = wf.readframes(frames_to_read)
            
            # 切り出した音声を一時ファイルに保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_chunk:
                chunk_path = temp_chunk.name
                with wave.open(chunk_path, 'wb') as chunk_wf:
                    chunk_wf.setnchannels(n_channels)
                    chunk_wf.setsampwidth(sampwidth)
                    chunk_wf.setframerate(framerate)
                    chunk_wf.writeframes(chunk_data)
            
            # APIにリクエスト送信
            try:
                print(f"Transcribing chunk {chunk_index + 1}...")
                with open(chunk_path, "rb") as file:
                    chunk_transcription = client.audio.transcriptions.create(
                        file=(os.path.basename(chunk_path), file.read()),
                        model="whisper-large-v3-turbo",
                        prompt="営業と顧客の会話です。日本語で出力してください。",
                        response_format="verbose_json",
                        timestamp_granularities=["word"]
                    )
                
                # タイムスタンプに「分割した分の時間（オフセット）」を加算して結合
                offset = chunk_index * CHUNK_LENGTH_SEC
                words = getattr(chunk_transcription, 'words', [])
                if not words and isinstance(chunk_transcription, dict):
                    words = chunk_transcription.get('words', [])
                    
                for w in words:
                    if isinstance(w, dict):
                        w['start'] += offset
                        w['end'] += offset
                        all_words.append(w)
                    else:
                        all_words.append({
                            'word': getattr(w, 'word', getattr(w, 'text', '')),
                            'start': getattr(w, 'start', 0.0) + offset,
                            'end': getattr(w, 'end', 0.0) + offset
                        })
                        
            finally:
                os.remove(chunk_path)  # 使い終わった分割ファイルを削除
                
            current_frame += frames_to_read
            chunk_index += 1
            
    print("Chunk transcription complete.")
    # tasks.py でそのまま扱えるように辞書型で返す
    return {"words": all_words}