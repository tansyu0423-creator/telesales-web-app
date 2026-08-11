# 📚 テレセールス見込み顧客スコアリングシステム 設計書ドキュメント

本プロジェクトの成果発表および保守運用に向けた仕様書・設計書一覧です。

---

## 📄 設計書一覧

1. [📐 システム全体構成・アーキテクチャ設計書](file:///home/SHUNTAF/Desktop/telesales_scoring/docs/01_system_architecture.md)
   - システム概要、採用技術スタック、全体アーキテクチャ図 (Mermaid)、処理パイプライン・シーケンス図
2. [🗄️ データベース設計書 (ER図・テーブル定義書)](file:///home/SHUNTAF/Desktop/telesales_scoring/docs/02_database_design.md)
   - PostgreSQL 16 DB構成、ER図、全テーブル物理定義 (`call_records`, `transcripts`, `analysis_results`)
3. [🌐 REST API 仕様書](file:///home/SHUNTAF/Desktop/telesales_scoring/docs/03_api_specification.md)
   - FastAPI REST API エンドポイント一覧、リクエスト/レスポンス詳細仕様、CSVエクスポート仕様
4. [🤖 AI / LLM プロンプト ＆ スコアリング仕様書](file:///home/SHUNTAF/Desktop/telesales_scoring/docs/04_llm_prompt_spec.md)
   - AIモデル一覧 (Whisper, Pyannote, Llama 3, Gemini 2.0 Flash)、プロンプト定義、Structured Output スコアリング基準、フォールバック設計
