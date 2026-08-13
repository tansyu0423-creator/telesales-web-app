# 🌐 REST API 仕様書 (API Specification)

## 1. ベースURL (Base URL)
- ローカル開発環境: `http://localhost:8000`
- API ドキュメント (Swagger UI): `http://localhost:8000/docs`

---

## 2. エンドポイント一覧

| メソッド | パス | タグ | 機能概要 |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Health | サーバー正常稼働確認 |
| `POST` | `/upload/` | Audio Upload | 音声ファイル (.wav / .mp3) を MinIO にアップロード |
| `GET` | `/audio/{filename}` | Audio Stream | MinIO から音声ファイルをダウンロード / ストリーミング再生 |
| `POST` | `/records/` | Call Records | 新しい通話レコードメタデータを登録 |
| `GET` | `/records/` | Call Records | 通話レコード一覧（トランスクリプト・分析結果含む）を取得 |
| `GET` | `/records/{record_id}` | Call Records | 指定IDの通話レコード詳細を取得 |
| `POST` | `/records/{record_id}/transcribe` | STT & Diarization | Whisper STT ＋ Pyannote話者分離 ＋ Llama3役割同定 ＋ Geminiスコアリングを一括実行 (Celery非同期) |
| `POST` | `/records/{record_id}/summarize` | Analysis | Gemini 2.0 Flash による通話要約＆シグナル抽出 |
| `POST` | `/records/{record_id}/score` | Analysis | Gemini Structured Output による S〜Eランクスコアリングの非同期実行 |
| `GET` | `/tasks/{task_id}` | Task Status | バックグラウンドCeleryタスクのステータス確認 (PENDING/STARTED/SUCCESS/FAILURE) |
| `GET` | `/records/{record_id}/export/csv` | Export | 通話メタデータ、成約率、AIスコア、対話文字起こしを含む CSV ダウンロード |

---

## 3. 各エンドポイント詳細仕様

### 3.1. ヘルスチェック API
`GET /health`

- **レスポンス (200 OK)**:
  ```json
  {
    "status": "ok"
  }
  ```

---

### 3.2. 音声ファイルアップロード API
`POST /upload/`

- **リクエスト**: `multipart/form-data`
  - `file`: 音声ファイル（許可拡張子: `.wav`, `.mp3`）
- **レスポンス (200 OK)**:
  ```json
  {
    "message": "ファイルのアップロードに成功しました",
    "original_filename": "sample_call.mp3",
    "saved_filename": "a1b2c3d4-e5f6-7890-abcd-123456789abc.mp3"
  }
  ```
- **エラーレスポンス**:
  - `400 Bad Request`: 許可されていない拡張子の場合
  - `500 Internal Server Error`: MinIO ストレージ保存エラー

---

### 3.3. 通話レコード登録 API
`POST /records/`

- **リクエストボディ (`application/json`)**:
  ```json
  {
    "sales_code": "REP-101",
    "customer_phone": "090-1234-5678",
    "call_duration": 180,
    "audio_file_path": "a1b2c3d4-e5f6-7890-abcd-123456789abc.mp3"
  }
  ```
- **レスポンス (200 OK)**: `CallRecord` スキーマオブジェクト

---

### 3.4. 通話レコード一覧取得 API
`GET /records/`

- **クエリパラメータ**:
  - `skip` (int, default: 0)
  - `limit` (int, default: 100)
- **レスポンス (200 OK)**: `CallRecord` オブジェクトの配列
  ```json
  [
    {
      "id": 1,
      "sales_code": "REP-101",
      "customer_phone": "090-1234-5678",
      "call_duration": 180,
      "audio_file_path": "sample.mp3",
      "created_at": "2026-08-13T04:47:38.230566",
      "transcripts": [
        {
          "id": 1,
          "call_record_id": 1,
          "speaker": "Sales",
          "text": "お世話になっております。",
          "start_time": 0.0,
          "end_time": 3.5
        }
      ],
      "analysis": {
        "id": 1,
        "call_record_id": 1,
        "rank": "S",
        "purchase_probability": 95.0,
        "customer_interest": "即時導入を希望。",
        "concerns": "特になし。",
        "recommended_action": "見積書を送付しクロージング完了させる。"
      }
    }
  ]
  ```

---

### 3.5. フルAI解析パイプライン API
`POST /records/{record_id}/transcribe`

- **処理概要**:
  1. Celery バックグラウンドタスク (`process_full_audio_pipeline_task`) に投函し、即座に 202 Accepted ＋ `task_id` を返却
  2. Worker が MinIO から音声を取得
  3. Groq Whisper による日本語文字起こしセグメント生成
  4. Pyannote Audio による話者分離タイムスタンプ取得
  5. Llama 3 70B による Sales vs Customer 役割同定
  6. DB (`transcripts`) への対話ログ一括保存
  7. Gemini 2.0 Flash による成約率・S〜Eランク判定・関心点・懸念点・推奨アクション抽出 ＆ DB (`analysis_results`) への保存
- **レスポンス (202 Accepted)**:
  ```json
  {
    "message": "AI解析パイプラインを開始しました",
    "task_id": "f9ae5af7-f55a-4392-a6b4-701a75a32561",
    "record_id": 1
  }
  ```

---

### 3.6. Celery タスクステータス確認 API
`GET /tasks/{task_id}`

- **レスポンス (200 OK - 処理完了)**:
  ```json
  {
    "task_id": "f9ae5af7-f55a-4392-a6b4-701a75a32561",
    "status": "SUCCESS",
    "result": {
      "status": "success",
      "record_id": 1,
      "transcript_count": 12,
      "rank": "S",
      "purchase_probability": 95.0
    }
  }
  ```

---

### 3.7. 通話分析レポート CSV エクスポート API
`GET /records/{record_id}/export/csv`

- **レスポンス (200 OK)**:
  - `Content-Type`: `text/csv; charset=utf-8`
  - `Content-Disposition`: `attachment; filename=record_1_report.csv`
  - **仕様**: 日本語 Excel で文字化けしないよう、レスポンス先頭に UTF-8 BOM (`\ufeff`) を付与。
