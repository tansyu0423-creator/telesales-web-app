# 🤖 AI / LLM プロンプト ＆ スコアリング仕様書

## 1. 採用モデルと役割分担 (Model Architecture)

| モデル名 | 提供事業者 | 処理タスク | 選定理由・特徴 |
| :--- | :--- | :--- | :--- |
| **`whisper-large-v3-turbo`** | Groq Cloud | 音声認識・文字起こし (STT) | 超高速推論 (リアルタイム比10倍以上)・日本語認識精度 |
| **`speaker-diarization-3.1`** | Pyannote / HuggingFace | 話者分離 (Speaker Diarization) | タイムスタンプ別話者セグメント抽出のデファクトスタンダード |
| **`llama-3.3-70b-versatile`** | Groq Cloud | 話者役割判定 (Role Identification) | 構造的対話推論・超低遅延レスポンス |
| **`gemini-2.0-flash`** | Google Cloud / Gemini API | 要約・シグナル抽出・見込みスコアリング | 大規模文脈受容・Native Structured Output (Pydantic連動) 強制 |

---

## 2. プロンプト設計仕様

### 2.1. 話者役割判定プロンプト (`backend/llm_analysis.py`)
アウトバウンド・テレセールスの構造的原則（発信側が先に名乗る）に基づき、Whisper＋Pyannoteの出力テキストから Sales（営業）と Customer（顧客）を厳密判定する。

```text
あなたはプロフェッショナルな音声対話解析AIです。以下のデータは「企業から顧客へかけたアウトバウンドのテレセールス（電話営業）」の文字起こしログです。
各セリフが「営業担当者（Sales）」のものか、「顧客（Customer）」のものかを論理的に判定してください。

【アウトバウンド・テレセールスの構造的原則】
1. 営業担当者 (Sales) の定義:
   - この通話は営業側から発信しているため、時間の流れにおいて最初に発言し、自社名や自身の名前を名乗る人物は必ず営業担当者です。
   - 用件の切り出し、「お時間よろしいでしょうか」というアポイントの打診、およびクロージングを行います。
2. 顧客 (Customer) の定義:
   - 営業からの呼びかけに対して応答する側です。
   - 「こんにちは」「お電話ありがとうございます」という第一声の応答や、自身の状況伝達を行います。

【会話ログ】
{full_sample}

【出力形式】
JSON形式で、各セリフのID（文字列の数字）をキー、判定結果（"Sales" または "Customer"）を値にしたオブジェクトのみを出力してください。
```

---

### 2.2. 通話要約 ＆ シグナル抽出プロンプト (`backend/summary_analysis.py`)
対話テキストから重要指標（要約・購買シグナル・ネガティブシグナル）をJSON抽出する。

```text
あなたはプロのインサイドセールス分析AIです。以下の電話営業の対話ログを分析し、JSON形式で結果を出力してください。

【対話ログ】
{dialogue_text}

【出力形式（必ず以下のJSONキーを含めること）】
{
    "summary": "通話全体の要約（200文字程度で簡潔に）",
    "buying_signals": ["顧客の肯定的な反応や、興味を示している点", "価格や導入時期に関する前向きな質問など"],
    "negative_signals": ["顧客が示した懸念点や難色", "時期尚早、価格への不満などのネガティブな反応"]
}
```

---

### 2.3. Gemini Structured Output スコアリングプロンプト (`backend/llm_analysis.py`)
Pydantic スキーマ `schemas.AnalysisResultBase` を `response_schema` に与え、型安全なランク判定を行う。

- **Pydantic スキーマ構造**:
  ```python
  class AnalysisResultBase(BaseModel):
      rank: str = Field(..., description="S, A, B, C, D, Eのいずれか1文字")
      purchase_probability: int = Field(..., ge=0, le=100, description="0から100までの整数（%）")
      customer_interest: str = Field(..., description="顧客が示唆した関心点や評価しているポイント")
      concerns: str = Field(..., description="顧客の懸念点、反論、またはボトルネック")
      recommended_action: str = Field(..., description="営業担当者が次にとるべき具体的な推奨アクション")
  ```

- **ランク定義基準 (Scoring Criteria)**:
  - **S ランク (購入確率 90〜100%)**: 即時導入意思あり、次回アポイント・見積提示確定
  - **A ランク (購入確率 70〜89%)**: 高い関心あり、予算・時期の具体化段階
  - **B ランク (購入確率 50〜69%)**: 前向きな興味あり、比較検討中
  - **C ランク (購入確率 30〜49%)**: 情報収集段階、強いニーズは未顕在
  - **D ランク (購入確率 10〜29%)**: 難色あり、現状維持派
  - **E ランク (購入確率 0〜9%)**: 担当者不在、明確な拒絶、ターゲット外

---

## 3. フェイルセーフ ＆ 冗長化機構 (Fallback Architecture)
1. **Gemini API レートリミット・障害発生時**:
   - `gemini-2.0-flash` の呼び出しで例外が発生した場合、自動的に Groq API (`llama-3.3-70b-versatile`) に切替。
2. **話者同定エラー時**:
   - 会話の先頭（発言者）をインサイドセールスの原則に基づき `Sales` と判定し、以降を交互・対話構造から補正するフォールバックロジックを保持。
