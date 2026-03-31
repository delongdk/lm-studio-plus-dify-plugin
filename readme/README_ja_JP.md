# LM Studio Plus — Dify プラグイン

**作者：** [delongdk](https://github.com/delongdk)  
**バージョン：** 0.0.1  
**タイプ：** model  

[LM Studio](https://lmstudio.ai/) のローカルモデルを [Dify](https://dify.ai/) に接続します。

## 背景

Dify マーケットプレイスの既存 [LM Studio プラグイン](https://github.com/stvlynn/lmstudio-Dify-Plugin) は実行時にエラーが発生し、メンテナンスが停止しているようです。**LM Studio Plus** は、スムーズに動作し、より多くの設定オプションをサポートする代替プラグインです。

## 機能

- **LLM（チャット＆補完）** — 両モードとも OpenAI 互換 `/v1/chat/completions` エンドポイントを使用
- **テキスト埋め込み** — `/v1/embeddings` エンドポイント対応
- **ストリーミング** — SSE によるリアルタイムトークンストリーミング
- **推論 / 思考** — `reasoning_content` のストリーミング出力（`<think>` タグ付き）
- **ツール呼び出し** — OpenAI function calling 形式対応、ストリーミングツールコール集約
- **ビジョン** — マルチモーダル画像入力対応（モデルごとに設定可能）
- **構造化出力** — `json_object` / `json_schema` の response_format 対応；スキーマをシステムプロンプトに自動挿入
- **API Key 認証** — オプションの API Key 対応、認証が有効な LM Studio サーバーへのアクセスに使用
- **カスタマイズ可能なパラメータ** — temperature、top_p、top_k、max_tokens、presence_penalty、frequency_penalty、repeat_penalty、seed

## 要件

- [LM Studio](https://lmstudio.ai/) をインストールし、少なくとも 1 つのモデルをロード
- LM Studio の API サーバーモードを有効化（デフォルトポート：`1234`）

## セットアップ

### 1. LM Studio

1. [LM Studio](https://lmstudio.ai/) をインストールして起動
2. ローカルモデルをロード（例：`lmstudio-community/qwen2.5-7b-instruct`）
3. ローカルサーバーを起動（Developer → Start Server）

![サーバー起動](../_assets/lm-studio-plus-02.png)

### 2. プラグインのインストール

Dify マーケットプレイスから **LM Studio Plus** を検索してインストール、またはソースから手動インストール。

### 3. モデルの追加

1. **設定 → モデルプロバイダー → LM Studio Plus → モデルを追加**

![モデル追加](../_assets/lm-studio-plus-01.png)

2. 入力項目：
   - **モデル名** — LM Studio に表示されるモデル ID（例：`qwen/qwen3-32b`）
   - **ベース URL** — LM Studio サーバーアドレス（デフォルト：`http://localhost:1234`）
   - **補完モード** — `チャット`（マルチターン）または `補完`（シングルプロンプト）
   - **コンテキストサイズ** / **最大トークン** — モデルに応じて調整
   - **ビジョンサポート** / **関数呼び出しサポート** — モデルが対応している場合は有効化

## 使用方法

セットアップ完了後、Dify アプリケーション（Chatbot、Agent、Workflow など）のモデルドロップダウンから設定済みの LM Studio モデルを選択してください。

## ライセンス

[MIT](../LICENSE)
