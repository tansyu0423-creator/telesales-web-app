# 🚀 テレセールス・アナリティクス・ダッシュボード システム仕様書

## 1. システム概要
本システム（テレセールス見込み顧客スコアリングシステム）は、アウトバウンド型電話営業（テレセールス）における通話音声を自動でテキスト化・話者識別し、最先端の生成AI（Gemini 2.0 Flash / Llama 3.3 70B）を用いて成約見込み度の判定（S〜Eランクスコアリング）、要約、シグナル抽出を行う高度AIインサイドセールス支援プラットフォームです。

---

## 2. 技術スタック (Tech Stack)

| カテゴリ | 採用技術・サービス | 用途・詳細 |
| :--- | :--- | :--- |
| **フロントエンド** | Vue 3 (Composition API), Vite | ダッシュボード画面構築・SPA |
| | Tailwind CSS (v3) | レスポンシブ＆ダークモードUIスタイリング |
| | Axios | REST API クライアント（Base URL一元管理） |
| **バックエンド** | Python 3.12, FastAPI, Uvicorn | 高速非同期 REST API サーバー |
| | Celery 5.4, Redis 7 | バックグラウンド非同期タスク処理キュー |
| | SQLAlchemy 2.0 (AsyncSession), Alembic | ORM / DBマイグレーション管理 |
| | Pydantic v2 | データバリデーション・Structured Output定義 |
| **AI / LLM** | Groq Whisper (whisper-large-v3-turbo) | 高精度・超高速日本語音声テキスト化 (STT) |
| | Pyannote Audio (speaker-diarization-3.1) | タイムスタンプ別話者分離 (Diarization) |
| | Groq Llama 3.3 70B (llama-3.3-70b-versatile) | 話者役割判定 (Sales vs Customer) |
| | Google Gemini API (gemini-2.0-flash) | 通話要約・シグナル抽出・Pydantic Structured Output スコアリング |
| **インフラ / DB** | PostgreSQL 16 (Docker) | メインリレーショナルデータベース |
| | MinIO (Docker) | S3互換オブジェクトストレージ (音声ファイル格納) |
| | Redis 7 (Docker) | Celery用インメモリメッセージブローカー / バックエンド |

---

## 3. 全体アーキテクチャ構成図

```mermaid
flowchart TB
    subgraph Frontend ["フロントエンド (Vue 3 + Tailwind CSS)"]
        UI[ダッシュボード画面 / HomeView.vue]
    end

    subgraph Backend ["バックエンド API (FastAPI)"]
        API[main.py Router]
        CRUD[crud.py / Async DB Layer]
    end

    subgraph TaskQueue ["タスク処理 (Celery + Redis)"]
        Redis[(Redis Message Broker)]
        Worker[Celery Worker / tasks.py]
        STT_MOD[stt.py / Groq Whisper]
        DIAR_MOD[diarization.py / Pyannote]
        LLM_ROLE[llm_analysis.py / Role Identifier]
        LLM_SCORE[llm_analysis.py / Gemini Scoring]
    end

    subgraph External_AI ["外部 AI サービス"]
        Groq_API[Groq Cloud API]
        HF_Hub[HuggingFace Hub]
        Gemini_API[Google Gemini API]
    end

    subgraph Infrastructure ["インフラストラクチャ (Docker Container)"]
        MinIO[(MinIO Object Storage)]
        Postgres[(PostgreSQL 16 DB)]
    end

    UI <-->|HTTP REST / Axios| API
    API -->|音声保存/再生| MinIO
    API -->|非同期タスクキュー投函| Redis
    Redis -->|タスク受信| Worker

    Worker --> STT_MOD
    Worker --> DIAR_MOD
    Worker --> LLM_ROLE
    Worker --> LLM_SCORE

    STT_MOD -->|STT API| Groq_API
    DIAR_MOD -->|Pyannote Model| HF_Hub
    LLM_ROLE -->|Llama 3| Groq_API
    LLM_SCORE -->|Structured Output| Gemini_API
    LLM_SCORE -.->|Fallback| Groq_API

    API --> CRUD
    Worker --> CRUD
    CRUD <-->|Asyncpg| Postgres
```

---

## 4. 通話処理シーケンス図 (非同期処理パイプライン)

```mermaid
sequenceDiagram
    autonumber
    actor User as 営業担当者 / 管理者
    participant FE as Vue 3 フロントエンド
    participant BE as FastAPI バックエンド
    participant Redis as Redis (Message Broker)
    participant Worker as Celery Worker (tasks.py)
    participant MinIO as MinIO ストレージ
    participant AI as AIモジュール (Whisper/Pyannote/Gemini)
    participant DB as PostgreSQL DB

    User->>FE: 音声ファイルアップロード
    FE->>BE: POST /upload/
    BE->>MinIO: 音声ファイル保存
    MinIO-->>BE: 保存用ファイル名返却
    BE-->>FE: アップロード成功レスポンス

    User->>FE: 「STT文字起こし」ボタンクリック
    FE->>BE: POST /records/{id}/transcribe
    BE->>Redis: transcribe_and_diarize_task キュー投入
    BE-->>FE: 即時レスポンス (200 OK + task_id)
    
    par バックグラウンド実行
        Redis->>Worker: タスク取得
        Worker->>MinIO: 音声ファイルダウンロード
        Worker->>AI: 1. Whisper STT (テキスト化)
        Worker->>AI: 2. Pyannote (話者分離)
        Worker->>AI: 3. 単語位置合わせ ＆ 句読点分割
        AI-->>Worker: 話者付タイムラインテキスト
        Worker->>DB: トランスクリプト保存
    and フロントエンドポーリング
        loop 2秒間隔でステータス確認
            FE->>BE: GET /tasks/{task_id}
            BE-->>FE: ステータス (PENDING / SUCCESS)
        end
    end
    FE->>User: ダッシュボードUI更新 (文字起こし完了表示)

    User->>FE: 「AIスコアリング」ボタンクリック
    FE->>BE: POST /records/{id}/score
    BE->>Redis: score_record_task キュー投入
    BE-->>FE: 即時レスポンス (200 OK + task_id)

    par バックグラウンド実行
        Redis->>Worker: タスク取得
        Worker->>DB: トランスクリプト取得
        Worker->>AI: Gemini / Groq LLM スコアリング
        AI-->>Worker: S〜Eランク, 成約確率, 推奨アクション (JSON)
        Worker->>DB: 分析結果保存 / 更新 (Upsert)
    and フロントエンドポーリング
        loop 2秒間隔でステータス確認
            FE->>BE: GET /tasks/{task_id}
            BE-->>FE: ステータス (PENDING / SUCCESS)
        end
    end
    FE->>User: ダッシュボードUI自動更新 (ランクバッジ・成約確率表示)
```

---

## 5. データベース設計書 (ER図)

```mermaid
erDiagram
    CALL_RECORD ||--o{ TRANSCRIPT : "1対多 (対話ログ)"
    CALL_RECORD ||--o| ANALYSIS_RESULT : "1対1 (AI分析結果)"

    CALL_RECORD {
        int id PK "通話レコードID"
        string sales_code "営業担当コード"
        string customer_phone "顧客電話番号"
        int call_duration "通話時間(秒)"
        string audio_file_path "音声ファイルパス"
        datetime created_at "登録日時"
    }

    TRANSCRIPT {
        int id PK "対話ID"
        int call_record_id FK "通話レコードID"
        string speaker "話者 (Sales/Customer)"
        text text "発言内容"
        float start_time "開始時間(秒)"
        float end_time "終了時間(秒)"
    }

    ANALYSIS_RESULT {
        int id PK "分析ID"
        int call_record_id FK "通話レコードID"
        string rank "S〜Eランク (S, A, B, C, D, E)"
        int purchase_probability "成約確率(0-100%)"
        text customer_interest "顧客関心点"
        text concerns "懸念点・反論"
        text recommended_action "推奨アクション"
    }
```

---

## 6. API設計書 (主要エンドポイント)

| HTTPメソッド | エンドポイント | 説明 | リクエスト / レスポンス仕様 |
| :--- | :--- | :--- | :--- |
| `POST` | `/upload/` | 音声ファイルアップロード | `multipart/form-data` ➔ 保存ファイル名返却 |
| `POST` | `/records/{id}/transcribe` | STT文字起こし ＆ 話者分離 | Whisper + Pyannote ＋ Llama3 実行 ＆ DB保存 |
| `POST` | `/records/{id}/summarize` | AI通話要約 ＆ シグナル抽出 | Gemini 2.0 Flash 実行（要約・シグナル返却） |
| `POST` | `/records/{id}/score` | AIスコアリング実行 | Gemini Structured Output 実行 ＆ DB保存 (Upsert) |
| `GET` | `/records/` | 全通話記録・分析結果の取得 | レスポンス: 一覧データ（JSON） |
| `GET` | `/records/{id}/export/csv` | CSVレポート出力 | レスポンス: BOM付き UTF-8 CSVファイル |
