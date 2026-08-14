# 🚀 テレセールス・アナリティクス・ダッシュボード システム仕様書

## 1. システム概要
本システム（テレセールス見込み顧客スコアリングシステム）は、アウトバウンド型電話営業（テレセールス）における通話音声を自動でテキスト化・話者識別し、最先端の生成AI（Gemini 2.0 Flash / Llama 3.3 70B）を用いて成約率の判定（S〜Eランクスコアリング）、要約、シグナル抽出を行う高度AIインサイドセールス支援プラットフォームです。

---

## 2. 技術スタック (Tech Stack)

| カテゴリ | 採用技術・サービス | 用途・詳細 |
| :--- | :--- | :--- |
| **フロントエンド** | Vue 3 (Composition API), Vite | ダッシュボード画面構築・SPA |
| | Tailwind CSS (v3) | レスポンシブ＆ダークモードUIスタイリング |
| | Pinia | アップロード状態管理・ストア |
| | Vue Router 4 | ルーティング制御（`/`, `/upload`, `/records/:id`） |
| | Axios | REST API クライアント（Base URL一元管理） |
| | Lucide Vue Next | モダンアイコンセット |
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

## 3. 分類ランク表記標準（Wording & Labeling Specifications）

本システムでは、顧客の反応およびAIスコアリング結果に基づき、以下の分類ランク基準を厳格に適用します。

| ランク | 正式名称 (パラメータ) | 成約率 (％) 基準 | UI表示ルール |
| :---: | :--- | :---: | :--- |
| **S** | **非常に有望** | 90% 〜 100% | 絞り込み: `[S：非常に有望]` ｜ カード右上: `S` ｜ パラメータ: `非常に有望` |
| **A** | **有望** | 70% 〜 89% | 絞り込み: `[A：有望]` ｜ カード右上: `A` ｜ パラメータ: `有望` |
| **B** | **検討中** | 50% 〜 69% | 絞り込み: `[B：検討中]` ｜ カード右上: `B` ｜ パラメータ: `検討中` |
| **C** | **観察** | 30% 〜 49% | 絞り込み: `[C：観察]` ｜ カード右上: `C` ｜ パラメータ: `観察` |
| **D** | **低可能性** | 10% 〜 29% | 絞り込み: `[D：低可能性]` ｜ カード右上: `D` ｜ パラメータ: `低可能性` |
| **E** | **不可行** | 0% 〜 9% | 絞り込み: `[E：不可行]` ｜ カード右上: `E` ｜ パラメータ: `不可行` |

- **表記統一ルール**:
  - `成約可能性（購入確率）` ➔ 必ず **`成約率`** と表記。
  - `文字起こし` ➔ **`AI解析`** または **`対話ログ`** と表記。
  - `専用詳細画面 ↗` ➔ **`詳細画面 ↗`** と表記。
  - `簡易表示 ▼ / 簡易表示閉じる ▲` ➔ **`表示 ▼ / 非表示 ▲`** と表記。

---

## 4. フロントエンド UI / UX 仕様

1. **ダッシュボード画面 (`HomeView.vue`)**:
   - **トップナビゲーションタブ**: `📋 通話データ一覧` と `👔 営業担当者別 パフォーマンス集計` の2タブ切替。
   - **営業担当者別パフォーマンス分析**: 担当者ごとの平均成約率、総通話数、S/Aランク獲得数、獲得ランク内訳バッジ（例: `非常に有望 ×2`）を集計・可視化。ワンタップでその担当者の通話履歴へドリルダウン絞り込み。
   - **2列〜3列 レスポンシブグリッドカード配置**: PC表示時は横3列 (`lg:grid-cols-3`)、タブレット表示時は横2列 (`md:grid-cols-2`) のカード配置。
   - **64px 拡大円形アニメーション成約率ゲージ**: スクロール進入検知（`IntersectionObserver`）により、画面視認時に 0% から目標％へ 3.8秒かけてゆったり優雅にリングと数字が拡大同期伸長。画面外スクロールアウト時は 0% にリセットされ、再視認時に再アニメーション。
2. **専用カスタム音声プレイヤー (`CustomAudioPlayer.vue`)**:
   - 音量コントロールはホバー/タップ時に**上向き縦型ポップオーバー** (`writing-mode: vertical-lr`) で展開し、再生タイムラインシークバーとの干渉を完全に防ぐ構造。
3. **新規アップロード画面 (`UploadView.vue`)**:
   - ファイル選択時に **`✖ 選択解除`** ボタンを完備。
   - Celery 解析完了時に成功通知を表示し、**1.5秒後にダッシュボード (`/`) へ自動リダイレクト**。
4. **日時タイムゾーン自動変換**:
   - DBに保存された UTC 日時 ISO 文字列に `Z` を自動補正し、JST（日本標準時 UTC+9, `YYYY/MM/DD HH:mm`）形式に正確に変換して表示。

---

## 5. 全体アーキテクチャ構成図

```mermaid
flowchart TB
    subgraph Frontend ["フロントエンド (Vue 3 + Tailwind CSS + Pinia)"]
        UI[HomeView.vue / DetailView.vue / UploadView.vue]
        Player[CustomAudioPlayer.vue]
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
    UI --- Player
    API -->|音声保存/ストリーミング| MinIO
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

## 6. 通話処理シーケンス図 (非同期処理パイプライン)

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

    User->>FE: 音声ファイル選択 ＆ メタデータ入力
    FE->>BE: POST /upload/ (音声アップロード)
    BE->>MinIO: 音声ファイル保存
    MinIO-->>BE: 保存用ユニークファイル名返却
    FE->>BE: POST /records/ (通話レコード登録)
    BE->>DB: レコード保存
    BE-->>FE: 登録成功レスポンス

    User->>FE: 「⚡ AI解析」ボタンクリック (またはアップロード時自動実行)
    FE->>BE: POST /records/{id}/transcribe
    BE->>Redis: process_full_audio_pipeline_task キュー投入
    BE-->>FE: 即時レスポンス (202 Accepted + task_id)
    
    par バックグラウンド実行
        Redis->>Worker: タスク取得
        Worker->>MinIO: 音声ファイルダウンロード
        Worker->>AI: 1. Whisper STT (テキスト化)
        Worker->>AI: 2. Pyannote (話者分離)
        Worker->>AI: 3. Llama 3 (話者役割判定 Sales vs Customer)
        AI-->>Worker: 話者識別付きタイムライン対話ログ
        Worker->>DB: トランスクリプト一括保存
        Worker->>AI: 4. Gemini 2.0 Flash (スコアリング ＆ 要約)
        AI-->>Worker: 成約率(%), S〜Eランク, 関心点, 懸念点, 推奨アクション
        Worker->>DB: 分析結果保存 (Upsert)
    and フロントエンドポーリング
        loop 2秒間隔でステータス確認
            FE->>BE: GET /tasks/{task_id}
            BE-->>FE: ステータス (PENDING / SUCCESS)
        end
    end
    FE->>User: 緑の成功通知表示 ➔ 1.5秒後にダッシュボードへ自動遷移
```
