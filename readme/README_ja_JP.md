# LM Studio Plus — Dify プラグイン

**作者：** [delongdk](https://github.com/delongdk)  
**バージョン：** 0.0.2
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
- **構造化出力** — 汎用 JSON モードと JSON Schema 制約に対応；スキーマをシステムプロンプトに自動挿入
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

以下のいずれかの方法でインストールできます。

#### 方法 A: GitHub Releases のビルド済みアセットを使う

1. 最新リリースから次のファイルをダウンロードします。
   - `lm_studio_plus-<version>.signed.difypkg`
   - `lm_studio_plus.public.pem`
2. Dify Community Edition でサードパーティ署名検証を有効にしている場合は、まず公開鍵を `plugin_daemon` から参照できる場所に配置します。

   ```bash
   mkdir -p docker/volumes/plugin_daemon/public_keys
   cp lm_studio_plus.public.pem docker/volumes/plugin_daemon/public_keys/
   ```

3. `plugin_daemon` にその公開鍵を設定します。

   ```yaml
   services:
     plugin_daemon:
       environment:
         FORCE_VERIFYING_SIGNATURE: true
         THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED: true
         THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS: /app/storage/public_keys/lm_studio_plus.public.pem
   ```

4. Dify を再起動してから、署名済みパッケージをアップロードします。

   ```bash
   cd docker
   docker compose down
   docker compose up -d
   ```

5. Dify の **設定 → プラグイン** から `lm_studio_plus-<version>.signed.difypkg` をアップロードします。

サードパーティ署名検証を有効にしていない場合は、未署名の `lm_studio_plus-<version>.difypkg` をそのままアップロードすることもできます。

#### 方法 B: ローカルでパッケージ化して署名する

プラグインのルートで次を実行します。

```bash
dify plugin package . -o lm_studio_plus-<version>.difypkg
dify signature generate -f certs/lm_studio_plus
dify signature sign lm_studio_plus-<version>.difypkg -p certs/lm_studio_plus.private.pem
dify signature verify lm_studio_plus-<version>.signed.difypkg -p certs/lm_studio_plus.public.pem
```

その後、上記の Dify 公開鍵設定手順を行い、署名済みパッケージをアップロードしてください。

> **注:** サードパーティ署名検証は Dify Community Edition でのみ利用できます。

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
