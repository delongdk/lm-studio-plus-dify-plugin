# LM Studio Plus — Dify 插件

**作者：** [delongdk](https://github.com/delongdk)  
**版本：** 0.0.2
**类型：** model  

将 [LM Studio](https://lmstudio.ai/) 本地模型接入 [Dify](https://dify.ai/)。

## 背景

Dify 插件市场现有的 [LM Studio 插件](https://github.com/stvlynn/lmstudio-Dify-Plugin) 运行时存在报错，且看起来已不再维护。**LM Studio Plus** 提供了另一种可顺利运行并支持更多配置选项的选择。

## 功能特性

- **LLM（对话 & 补全）** — 两种模式均通过 OpenAI 兼容的 `/v1/chat/completions` 接口
- **文本嵌入** — 通过 `/v1/embeddings` 接口
- **流式输出** — 基于 SSE 的实时 token 流式传输
- **推理/思考** — 流式输出 `reasoning_content`，自动包裹 `<think>` 标签
- **工具调用** — 支持 OpenAI function calling 格式，流式工具调用聚合
- **视觉识别** — 支持多模态图像输入（可按模型配置）
- **结构化输出** — 支持通用 JSON 模式和 JSON Schema 约束；schema 自动注入系统提示词
- **API Key 认证** — 可选的 API Key 支持，用于访问启用了认证的 LM Studio 服务器
- **可自定义参数** — temperature、top_p、top_k、max_tokens、presence_penalty、frequency_penalty、repeat_penalty、seed

## 环境要求

- 安装并运行 [LM Studio](https://lmstudio.ai/)，至少加载一个模型
- 启用 LM Studio 的 API 服务器模式（默认端口：`1234`）

## 使用方法

### 1. LM Studio 配置

1. 安装并打开 [LM Studio](https://lmstudio.ai/)
2. 加载一个本地模型（如 `lmstudio-community/qwen2.5-7b-instruct`）
3. 启动本地服务器（Developer → Start Server）

![启动服务器](./_assets/lm-studio-plus-02.png)

### 2. 安装插件

可按以下任一方式安装：

#### 方案 A：使用 GitHub Releases 中已打好的文件

1. 下载最新 release 资产：
   - `lm_studio_plus-<version>.signed.difypkg`
   - `lm_studio_plus.public.pem`
2. 如果你的 Dify Community Edition 开启了第三方签名校验，请先把公钥放到 `plugin_daemon` 可访问的位置：

   ```bash
   mkdir -p docker/volumes/plugin_daemon/public_keys
   cp lm_studio_plus.public.pem docker/volumes/plugin_daemon/public_keys/
   ```

3. 在 `plugin_daemon` 中配置该公钥：

   ```yaml
   services:
     plugin_daemon:
       environment:
         FORCE_VERIFYING_SIGNATURE: true
         THIRD_PARTY_SIGNATURE_VERIFICATION_ENABLED: true
         THIRD_PARTY_SIGNATURE_VERIFICATION_PUBLIC_KEYS: /app/storage/public_keys/lm_studio_plus.public.pem
   ```

4. 重启 Dify，然后在 Dify 中上传签名包：

   ```bash
   cd docker
   docker compose down
   docker compose up -d
   ```

5. 进入 **设置 → 插件**，上传 `lm_studio_plus-<version>.signed.difypkg`。

如果未开启第三方签名校验，也可以直接上传未签名的 `lm_studio_plus-<version>.difypkg`。

#### 方案 B：本地打包并签名

在插件根目录执行：

```bash
dify plugin package . -o lm_studio_plus-<version>.difypkg
dify signature generate -f certs/lm_studio_plus
dify signature sign lm_studio_plus-<version>.difypkg -p certs/lm_studio_plus.private.pem
dify signature verify lm_studio_plus-<version>.signed.difypkg -p certs/lm_studio_plus.public.pem
```

然后按上面的 Dify 公钥配置步骤完成配置，并上传签名包。

> **说明：** 第三方签名校验目前仅适用于 Dify Community Edition。

### 3. 添加模型

1. 进入 **设置 → 模型供应商 → LM Studio Plus → 添加模型**

![添加模型](./_assets/lm-studio-plus-01.png)

2. 填写：
   - **模型名称** — LM Studio 中显示的模型标识（如 `qwen/qwen3-32b`）
   - **基础 URL** — LM Studio 服务器地址（默认：`http://localhost:1234`）
   - **模型类型** — `对话`（多轮）或 `补全`（单轮）
   - **上下文长度** / **最大 token 上限** — 根据模型调整
   - **Vision 支持** / **函数调用支持** — 如模型支持则开启

## 使用

配置完成后，在 Dify 应用（Chatbot、Agent、Workflow 等）的模型下拉菜单中选择已配置的 LM Studio 模型即可。

## 许可证

[MIT](../LICENSE)
