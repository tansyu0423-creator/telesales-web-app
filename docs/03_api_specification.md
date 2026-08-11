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
| `POST` | `/records/{record_id}/transcribe` | STT & Diarization | Whisper STT ＋ Pyannote話者分離 ＋ LLM役割同定の実行・保存 |
| `POST` | `/records/{record_id}/summarize` | Analysis | Gemini 2.0 Flash による通話要約＆シグナル抽出 |
| `POST` | `/records/{record_id}/score` | Analysis | Gemini Structured Output による S〜Eランクスコアリング＆DB保存 |
| `GET` | `/records/{record_id}/export/csv` | Export | 通話メタデータ、AIスコア、文字起こしを含む CSV ダウンロード |

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
    "original_filename": "sample_call.wav",
    "saved_filename": "a1b2c3d4-e5f6-7890-abcd-123456789abc.wav"
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
    "sales_code": "SALES_001",
    "customer_phone": "090-1234-5678",
    "call_duration": 180,
    "audio_file_path": "a1b2c3d4-e5f6-7890-abcd-123456789abc.wav"
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

---

### 3.5. STT文字起こし ＆ 話者分離パイプライン API
`POST /records/{record_id}/transcribe`

- **処理概要**:
  1. MinIO から音声を取得
  2. Groq Whisper による日本語文字起こしセグメント生成
  3. Pyannote Audio による話者分離タイムスタンプ取得
  4. 時間重複計算 ＆ Groq Llama 3.3 70B による 「Sales / Customer」 役割判定
  5. DB (`transcripts`) へのクリア＆一括保存
- **レスポンス (200 OK)**:
  ```json
  {
    "status": "success",
    "message": "Whisper STT ＋ Pyannote話者分離 ＋ LLM役割構造化が完了しました",
    "record_id": 1
  }
  ```

---

### 3.6. AI通話要約 ＆ シグナル抽出 API
`POST /records/{record_id}/summarize`

- **処理概要**:
  - トランスクリプトを取得し、Gemini 2.0 Flash（代替: Groq Llama 3.3）にて要約・シグナル抽出を実行
- **レスポンス (200 OK)**:
  ```json
  {
    "status": "success",
    "record_id": 1,
    "analysis": {
      "summary": "商材の費用対効果について説明し、好触感を得た通話。",
      "buying_signals": [
        "価格体系と導入スケジュールについての具体的な質問",
        "社内検討のための資料請求"
      ],
      "negative_signals": [
        "初期導入コストに対する一時的な難色"
      ]
    }
  }
  ```

---

### 3.7. AIスコアリング ＆ DB保存 API
`POST /records/{record_id}/score`

- **処理概要**:
  - トランスクリプトを取得し、Gemini 2.0 Flash の Native Structured Output（Pydantic スキーマ受容）で S〜E ランクおよび成約確率を算出。DB (`analysis_results`) に Upsert 保存。
- **レスポンス (200 OK)**:
  ```json
  {
    "status": "success",
    "record_id": 1,
    "message": "スコアリングとデータベースへの保存が完了しました",
    "analysis_result": {
      "rank": "A",
      "purchase_probability": 85,
      "customer_interest": "業務自動化によるコスト削減効果",
      "concerns": "既存システムからのデータ移行期間",
      "recommended_action": "データ移行手順書を添付したお礼メールを送付し、次週デモ日程を確定する"
    }
  }
  ```

---

### 3.8. 通話分析レポート CSV エクスポート API
`GET /records/{record_id}/export/csv`

- **レスポンス (200 OK)**:
  - `Content-Type`: `text/csv; charset=utf-8`
  - `Content-Disposition`: `attachment; filename=report_1.csv`
  - **仕様**: 日本語 Excel で文字化けしないよう、レスポンス先頭に UTF-8 BOM (`\ufeff`) を付与。
