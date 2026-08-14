import os
import wave
import numpy as np
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

def diarize_audio(file_path: str) -> List[Dict[str, Any]]:
    hf_token = os.getenv("HUGGINGFACE_TOKEN", "")
    
    if hf_token:
        try:
            from pyannote.audio import Pipeline
            import torch

            print("Loading Pyannote model... (Using v3.0.0)")
            
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.0.0",
                token=hf_token
            )
            
            if pipeline is None:
                raise RuntimeError("Failed to load Pyannote pipeline.")
            
            if torch.cuda.is_available():
                pipeline.to(torch.device("cuda"))

            print("Starting diarization inference...")
            
            # OSのエラーを回避するPython標準の読み込み
            with wave.open(file_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                audio_data = wf.readframes(n_frames)
                
                data = np.frombuffer(audio_data, dtype=np.int16)
                data = data.astype(np.float32) / 32768.0
                waveform = torch.from_numpy(data).unsqueeze(0)

            # AI推論の実行
            diarization = pipeline({"waveform": waveform, "sample_rate": sample_rate})
            
            segments = []
            
            # --- 【強化版】どんな箱で返ってきても確実に取り出すロジック ---
            if hasattr(diarization, "itertracks"):
                # 通常のむき出しデータの場合
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    segments.append({"start": turn.start, "end": turn.end, "speaker_id": speaker})
            else:
                # DiarizeOutputなどの箱に包まれている場合、動的に箱を開ける
                print(f"Detected wrapper object: {type(diarization)}. Extracting dynamically...")
                for attr_name in dir(diarization):
                    attr_val = getattr(diarization, attr_name)
                    if hasattr(attr_val, "itertracks"):
                        for turn, _, speaker in attr_val.itertracks(yield_label=True):
                            segments.append({"start": turn.start, "end": turn.end, "speaker_id": speaker})
                        break
                
                # 万が一箱が開かなかった場合の最終手段（文字列解析）
                if not segments:
                    try:
                        for line in str(diarization).split('\n'):
                            if line.startswith("SPEAKER"):
                                parts = line.split()
                                if len(parts) >= 8:
                                    segments.append({
                                        "start": float(parts[3]),
                                        "end": float(parts[3]) + float(parts[4]),
                                        "speaker_id": parts[7]
                                    })
                    except Exception:
                        pass

            if not segments:
                raise ValueError(f"Could not extract segments from {type(diarization)}")

            print(f"Diarization complete! Extracted {len(segments)} segments.")
            return segments
        
        except Exception as e:
            import traceback
            print(f"pyannote.audio Error, using fallback: {e}")
            traceback.print_exc()

    # フォールバック（モックデータ）
    print("Using mock diarization data...")
    return [
        {"start": 0.0, "end": 4.5, "speaker_id": "SPEAKER_00"},
        {"start": 4.6, "end": 10.0, "speaker_id": "SPEAKER_01"},
        {"start": 10.1, "end": 18.0, "speaker_id": "SPEAKER_00"},
        {"start": 18.1, "end": 25.0, "speaker_id": "SPEAKER_01"},
    ]