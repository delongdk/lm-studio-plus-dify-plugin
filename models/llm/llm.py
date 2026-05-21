import json
import logging
import re
from collections.abc import Generator
from decimal import Decimal
from typing import Any, Optional, Union, cast

import requests
from dify_plugin.entities.model import (
    AIModelEntity,
    DefaultParameterName,
    FetchFrom,
    I18nObject,
    ModelFeature,
    ModelPropertyKey,
    ModelType,
    ParameterRule,
    ParameterType,
    PriceConfig,
)
from dify_plugin.entities.model.llm import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    ImagePromptMessageContent,
    PromptMessage,
    PromptMessageContentType,
    PromptMessageTool,
    SystemPromptMessage,
    TextPromptMessageContent,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
    InvokeRateLimitError,
    InvokeServerUnavailableError,
)
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel

logger = logging.getLogger(__name__)

_MAX_TOOL_CALLS = 1000
_TRUTHY_VALUES = {"true", "supported", "yes", "1"}
_THINK_PATTERN = re.compile(r"^<think>.*?</think>\s*", re.DOTALL)


class LmStudioPlusLargeLanguageModel(LargeLanguageModel):
    """
    Model class for LM Studio Plus large language model.
    Uses OpenAI-compatible /v1/chat/completions endpoint for all modes.
    """

    @staticmethod
    def _drop_thinking_content(prompt_messages: list[PromptMessage]) -> None:
        """Remove <think>...</think> blocks from assistant messages to avoid
        wasting tokens and confusing the model in multi-turn conversations."""
        for p in prompt_messages:
            if not isinstance(p, AssistantPromptMessage):
                continue
            if not isinstance(p.content, str):
                continue
            if not p.content.startswith("<think>"):
                continue
            new_content = _THINK_PATTERN.sub("", p.content, count=1)
            if new_content != p.content:
                p.content = new_content

    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[list[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
    ) -> Union[LLMResult, Generator]:
        # Clean thinking content from previous assistant messages
        self._drop_thinking_content(prompt_messages)

        return self._generate(
            model=model,
            credentials=credentials,
            prompt_messages=prompt_messages,
            model_parameters=model_parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            user=user,
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: Optional[list[PromptMessageTool]] = None,
    ) -> int:
        return self._num_tokens_from_messages(prompt_messages)

    def validate_credentials(self, model: str, credentials: dict) -> None:
        try:
            self._generate(
                model=model,
                credentials=credentials,
                prompt_messages=[UserPromptMessage(content="ping")],
                model_parameters={"max_tokens": 5},
                stream=False,
            )
        except InvokeError as ex:
            raise CredentialsValidateFailedError(
                f"An error occurred during credentials validation: {ex.description}"
            )
        except Exception as ex:
            raise CredentialsValidateFailedError(
                f"An error occurred during credentials validation: {str(ex)}"
            )

    def _get_api_url(self, credentials: dict) -> str:
        base_url = credentials.get("base_url", "http://localhost:1234")
        if base_url.endswith("/"):
            base_url = base_url.rstrip("/")
        return base_url

    def _get_headers(self, credentials: dict) -> dict:
        api_key = credentials.get("api_key", "lm-studio")
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _generate(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[list[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
    ) -> Union[LLMResult, Generator]:
        base_url = self._get_api_url(credentials)
        headers = self._get_headers(credentials)

        # Always use OpenAI-compatible endpoint /v1/chat/completions
        # for both Chat and Completion modes.
        #
        # LM Studio does support /v1/completions (legacy endpoint), but it is
        # designed for base models only — prompt template is NOT applied, and
        # using it with chat-tuned models produces unexpected tokens.
        # See: https://lmstudio.ai/docs/developer/openai-compat/completions
        #
        # The native /api/v1/chat is also unsuitable: it only accepts a single
        # input (no multi-turn history), has no tool calling, no response_format,
        # and uses a different SSE event format.
        #
        # Therefore both Chat and Completion modes route to /v1/chat/completions.
        # The "mode" credential only affects the Dify UI (Chat = multi-message
        # editor, Completion = single prompt box).
        endpoint_url = f"{base_url}/v1/chat/completions"
        data: dict[str, Any] = {
            "model": model,
            "messages": [
                self._convert_prompt_message_to_dict(m) for m in prompt_messages
            ],
            "stream": stream,
        }
        if tools:
            data["tools"] = [
                self._convert_prompt_message_tool_to_dict(tool) for tool in tools
            ]

        # Map model parameters
        param_mapping = {
            "temperature": "temperature",
            "top_p": "top_p",
            "top_k": "top_k",
            "max_tokens": "max_tokens",
            "presence_penalty": "presence_penalty",
            "frequency_penalty": "frequency_penalty",
            "repeat_penalty": "repeat_penalty",
            "seed": "seed",
        }
        for param_key, api_key in param_mapping.items():
            if param_key in model_parameters and model_parameters[param_key] is not None:
                data[api_key] = model_parameters[param_key]

        # Handle structured output settings.
        # LM Studio only accepts response_format.type of "json_schema" or "text",
        # not "json_object". So generic JSON mode is represented by a permissive
        # JSON schema, and an explicit json_schema parameter overrides that fallback.
        if "format" in model_parameters:
            fmt = model_parameters["format"]
            if fmt == "json":
                data["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "json_object",
                        "strict": False,
                        "schema": {},
                    },
                }

        if "json_schema" in model_parameters:
            json_schema_str = model_parameters.get("json_schema", "")
            if json_schema_str:
                try:
                    schema_obj = json.loads(json_schema_str)
                    # If schema_obj already has "name" and "schema" keys, use it directly
                    if "name" in schema_obj and "schema" in schema_obj:
                        if "strict" not in schema_obj:
                            schema_obj["strict"] = True
                        data["response_format"] = {
                            "type": "json_schema",
                            "json_schema": schema_obj,
                        }
                    else:
                        # Treat the whole object as the schema itself
                        data["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "custom_schema",
                                "strict": True,
                                "schema": schema_obj,
                            },
                        }
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON Schema string, ignoring format")

                # Also inject schema into system prompt to guide model output
                structured_output_prompt = (
                    "Your response must be a JSON object that validates against "
                    "the following JSON schema, and nothing else.\n"
                    f"JSON Schema: ```json\n{json_schema_str}\n```"
                )
                messages = data.get("messages", [])
                system_msg = next(
                    (m for m in messages if m.get("role") == "system"), None
                )
                if system_msg:
                    system_msg["content"] = (
                        structured_output_prompt + "\n\n" + system_msg["content"]
                    )
                else:
                    messages.insert(
                        0, {"role": "system", "content": structured_output_prompt}
                    )
                    data["messages"] = messages

        if stop:
            data["stop"] = stop

        if user:
            data["user"] = user

        response = requests.post(
            endpoint_url, headers=headers, json=data, timeout=(10, 300), stream=stream
        )
        response.encoding = "utf-8"

        if response.status_code != 200:
            raise InvokeError(
                f"API request failed with status code {response.status_code}: {response.text}"
            )

        if stream:
            return self._handle_stream_response(
                model, credentials, response, prompt_messages
            )
        return self._handle_response(
            model, credentials, response, prompt_messages
        )

    def _handle_response(
        self,
        model: str,
        credentials: dict,
        response: requests.Response,
        prompt_messages: list[PromptMessage],
    ) -> LLMResult:
        response_json = response.json()

        # OpenAI-compatible response format
        choice = response_json.get("choices", [{}])[0]
        message = choice.get("message", {})
        response_content = ""
        # Handle reasoning content (support both field names)
        reasoning_content = message.get("reasoning") or message.get("reasoning_content", "")
        if reasoning_content:
            response_content += f"<think>\n{reasoning_content}\n</think>\n"
        response_content += message.get("content", "") or ""
        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tool_calls.append(self._extract_response_tool_call(tc))

        assistant_message = AssistantPromptMessage(
            content=response_content, tool_calls=tool_calls
        )

        usage_data = response_json.get("usage", {})
        prompt_tokens = usage_data.get(
            "prompt_tokens",
            self._get_num_tokens_by_gpt2(prompt_messages[0].content),
        )
        completion_tokens = usage_data.get(
            "completion_tokens",
            self._get_num_tokens_by_gpt2(response_content),
        )

        usage = self._calc_response_usage(
            model, credentials, prompt_tokens, completion_tokens
        )

        return LLMResult(
            model=model,
            prompt_messages=prompt_messages,
            message=assistant_message,
            usage=usage,
        )

    def _handle_stream_response(
        self,
        model: str,
        credentials: dict,
        response: requests.Response,
        prompt_messages: list[PromptMessage],
    ) -> Generator:
        yield from self._handle_openai_compat_stream(
            model, credentials, response, prompt_messages
        )

    def _handle_openai_compat_stream(
        self,
        model: str,
        credentials: dict,
        response: requests.Response,
        prompt_messages: list[PromptMessage],
    ) -> Generator:
        """Handle OpenAI-compatible /v1/chat/completions streaming."""
        full_text = ""
        chunk_index = 0
        tool_calls_by_index: dict[int, AssistantPromptMessage.ToolCall] = {}
        finish_reason: Optional[str] = None
        prompt_tokens = 0
        completion_tokens = 0
        has_usage = False
        is_reasoning = False  # Track reasoning state for <think> tag wrapping

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue

            # SSE format: "data: {...}" or "data: [DONE]"
            if line.startswith("data: "):
                data_str = line[6:]
            else:
                continue

            if data_str.strip() == "[DONE]":
                break

            try:
                chunk_json = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choice = (chunk_json.get("choices") or [{}])[0]
            delta = choice.get("delta", {})
            choice_finish_reason = choice.get("finish_reason")

            # Extract usage from the chunk if available
            usage_data = chunk_json.get("usage")
            if usage_data:
                prompt_tokens = usage_data.get("prompt_tokens", 0)
                completion_tokens = usage_data.get("completion_tokens", 0)
                has_usage = True

            # Handle tool calls in delta
            if delta.get("tool_calls"):
                for tc_delta in delta["tool_calls"]:
                    idx = tc_delta.get("index", 0)
                    if idx >= _MAX_TOOL_CALLS:
                        continue

                    existing = tool_calls_by_index.get(idx)
                    func_data = tc_delta.get("function", {})
                    if existing is None:
                        tc_id = tc_delta.get("id") or str(idx)
                        tool_calls_by_index[idx] = AssistantPromptMessage.ToolCall(
                            id=tc_id,
                            type="function",
                            function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                                name=func_data.get("name", ""),
                                arguments=func_data.get("arguments", ""),
                            ),
                        )
                    else:
                        if func_data.get("name"):
                            existing.function.name = func_data["name"]
                        if func_data.get("arguments"):
                            existing.function.arguments += func_data["arguments"]

            # Handle reasoning/thinking content in delta
            # Support both 'reasoning' (vLLM >= 0.17.1) and 'reasoning_content' (standard)
            reasoning_text = delta.get("reasoning") or delta.get("reasoning_content") or ""
            if reasoning_text:
                if not is_reasoning:
                    is_reasoning = True
                    yield LLMResultChunk(
                        model=model,
                        prompt_messages=prompt_messages,
                        delta=LLMResultChunkDelta(
                            index=chunk_index,
                            message=AssistantPromptMessage(content="<think>\n"),
                        ),
                    )
                    chunk_index += 1
                full_text += reasoning_text
                yield LLMResultChunk(
                    model=model,
                    prompt_messages=prompt_messages,
                    delta=LLMResultChunkDelta(
                        index=chunk_index,
                        message=AssistantPromptMessage(content=reasoning_text),
                    ),
                )
                chunk_index += 1

            # Handle text content in delta
            text = delta.get("content") or ""

            if text:
                # Close reasoning tag if transitioning from reasoning to content
                if is_reasoning:
                    is_reasoning = False
                    yield LLMResultChunk(
                        model=model,
                        prompt_messages=prompt_messages,
                        delta=LLMResultChunkDelta(
                            index=chunk_index,
                            message=AssistantPromptMessage(content="\n</think>\n"),
                        ),
                    )
                    chunk_index += 1
                full_text += text
                yield LLMResultChunk(
                    model=model,
                    prompt_messages=prompt_messages,
                    delta=LLMResultChunkDelta(
                        index=chunk_index,
                        message=AssistantPromptMessage(content=text),
                    ),
                )
                chunk_index += 1

            if choice_finish_reason:
                # Close reasoning tag if stream ends while still reasoning
                if is_reasoning:
                    is_reasoning = False
                    yield LLMResultChunk(
                        model=model,
                        prompt_messages=prompt_messages,
                        delta=LLMResultChunkDelta(
                            index=chunk_index,
                            message=AssistantPromptMessage(content="\n</think>\n"),
                        ),
                    )
                    chunk_index += 1
                finish_reason = choice_finish_reason

        # Yield tool calls if any
        if tool_calls_by_index:
            sorted_tool_calls = [
                tool_calls_by_index[i] for i in sorted(tool_calls_by_index)
            ]
            yield LLMResultChunk(
                model=model,
                prompt_messages=prompt_messages,
                delta=LLMResultChunkDelta(
                    index=chunk_index,
                    message=AssistantPromptMessage(
                        content="", tool_calls=sorted_tool_calls
                    ),
                    finish_reason="tool_calls",
                ),
            )
            chunk_index += 1

        # Final chunk with usage
        if not has_usage:
            prompt_tokens = self._num_tokens_from_messages(prompt_messages)
            completion_tokens = self._get_num_tokens_by_gpt2(full_text)

        usage = self._calc_response_usage(
            model, credentials, prompt_tokens, completion_tokens
        )
        yield LLMResultChunk(
            model=model,
            prompt_messages=prompt_messages,
            delta=LLMResultChunkDelta(
                index=chunk_index,
                message=AssistantPromptMessage(content=""),
                finish_reason=finish_reason or "stop",
                usage=usage,
            ),
        )

    def _convert_prompt_message_tool_to_dict(self, tool: PromptMessageTool) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    def _convert_prompt_message_to_dict(self, message: PromptMessage) -> dict:
        if isinstance(message, UserPromptMessage):
            message = cast(UserPromptMessage, message)
            if isinstance(message.content, str):
                return {"role": "user", "content": message.content}
            elif isinstance(message.content, list):
                content_parts = []
                for msg_content in message.content:
                    if msg_content.type == PromptMessageContentType.TEXT:
                        msg_content = cast(TextPromptMessageContent, msg_content)
                        content_parts.append(
                            {"type": "text", "text": msg_content.data}
                        )
                    elif msg_content.type == PromptMessageContentType.IMAGE:
                        msg_content = cast(ImagePromptMessageContent, msg_content)
                        image_url = msg_content.data
                        if not image_url.startswith(("http://", "https://", "data:")):
                            image_url = f"data:image/png;base64,{image_url}"
                        content_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            }
                        )
                return {"role": "user", "content": content_parts}
        elif isinstance(message, AssistantPromptMessage):
            message = cast(AssistantPromptMessage, message)
            msg_dict: dict[str, Any] = {
                "role": "assistant",
                "content": message.content,
            }
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            return msg_dict
        elif isinstance(message, SystemPromptMessage):
            message = cast(SystemPromptMessage, message)
            return {"role": "system", "content": message.content}
        elif isinstance(message, ToolPromptMessage):
            message = cast(ToolPromptMessage, message)
            msg_dict = {"role": "tool", "content": message.content}
            if hasattr(message, "tool_call_id") and message.tool_call_id:
                msg_dict["tool_call_id"] = message.tool_call_id
            return msg_dict

        raise ValueError(f"Unknown message type: {type(message)}")

    def _extract_response_tool_call(
        self, response_tool_call: dict
    ) -> AssistantPromptMessage.ToolCall:
        function_data = response_tool_call.get("function", {})
        arguments = function_data.get("arguments", "")
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments)
        return AssistantPromptMessage.ToolCall(
            id=response_tool_call.get("id", ""),
            type="function",
            function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                name=function_data.get("name", ""),
                arguments=arguments,
            ),
        )

    def _num_tokens_from_messages(self, messages: list[PromptMessage]) -> int:
        num_tokens = 0
        messages_dict = [self._convert_prompt_message_to_dict(m) for m in messages]
        for message in messages_dict:
            for key, value in message.items():
                num_tokens += self._get_num_tokens_by_gpt2(str(key))
                num_tokens += self._get_num_tokens_by_gpt2(str(value))
        return num_tokens

    def get_customizable_model_schema(
        self, model: str, credentials: dict
    ) -> AIModelEntity:
        features: list[ModelFeature] = []
        if credentials.get("vision_support") == "true":
            features.append(ModelFeature.VISION)
        fc_supported = str(credentials.get("function_call_support", "")).lower() in _TRUTHY_VALUES
        if fc_supported:
            features.append(ModelFeature.TOOL_CALL)
            features.append(ModelFeature.MULTI_TOOL_CALL)
            features.append(ModelFeature.STREAM_TOOL_CALL)

        entity = AIModelEntity(
            model=model,
            label=I18nObject(zh_Hans=model, en_US=model),
            model_type=ModelType.LLM,
            fetch_from=FetchFrom.CUSTOMIZABLE_MODEL,
            features=features,
            model_properties={
                ModelPropertyKey.MODE: credentials.get("mode", "chat"),
                ModelPropertyKey.CONTEXT_SIZE: int(
                    credentials.get("context_size", 4096)
                ),
            },
            parameter_rules=[
                ParameterRule(
                    name=DefaultParameterName.TEMPERATURE.value,
                    use_template=DefaultParameterName.TEMPERATURE.value,
                    label=I18nObject(en_US="Temperature", zh_Hans="温度"),
                    type=ParameterType.FLOAT,
                    help=I18nObject(
                        en_US="Controls randomness of the output. A higher value (e.g., 1.0) makes output more random, while a lower value (e.g., 0.1) makes it more deterministic. (Default: 0.7)",
                        zh_Hans="控制输出的随机性。较高的值（例如1.0）使输出更随机，较低的值（例如0.1）使输出更确定。（默认值：0.7）",
                    ),
                ),
                ParameterRule(
                    name=DefaultParameterName.TOP_P.value,
                    use_template=DefaultParameterName.TOP_P.value,
                    label=I18nObject(en_US="Top P", zh_Hans="Top P"),
                    type=ParameterType.FLOAT,
                    help=I18nObject(
                        en_US="Works together with top-k. A higher value (e.g., 0.95) will lead to more diverse text, while a lower value (e.g., 0.5) will generate more focused and conservative text. (Default: 0.9)",
                        zh_Hans="与top-k一起工作。较高的值（例如0.95）会导致生成更多样化的文本，而较低的值（例如0.5）会生成更专注和保守的文本。（默认值：0.9）",
                    ),
                    default=0.9,
                    min=0,
                    max=1,
                ),
                ParameterRule(
                    name="top_k",
                    label=I18nObject(en_US="Top K", zh_Hans="Top K"),
                    type=ParameterType.INT,
                    help=I18nObject(
                        en_US="Reduces the probability of generating nonsense. A higher value (e.g. 100) will give more diverse answers, while a lower value (e.g. 10) will be more conservative. (Default: 40)",
                        zh_Hans="减少生成无意义内容的可能性。较高的值（如100）将提供更多样化的答案，较低的值（如10）将更为保守。（默认值：40）",
                    ),
                    min=1,
                    max=100,
                ),
                ParameterRule(
                    name="max_tokens",
                    use_template="max_tokens",
                    label=I18nObject(en_US="Max Tokens", zh_Hans="最大令牌数"),
                    type=ParameterType.INT,
                    default=512
                    if int(credentials.get("max_tokens", 4096)) >= 768
                    else 128,
                    min=1,
                    max=int(credentials.get("max_tokens", 4096)),
                ),
                ParameterRule(
                    name="presence_penalty",
                    use_template="presence_penalty",
                    label=I18nObject(en_US="Presence Penalty", zh_Hans="存在惩罚"),
                    type=ParameterType.FLOAT,
                    help=I18nObject(
                        en_US="Penalizes new tokens based on whether they appear in the text so far.",
                        zh_Hans="根据新令牌是否已出现在文本中进行惩罚。",
                    ),
                    min=-2,
                    max=2,
                ),
                ParameterRule(
                    name="frequency_penalty",
                    use_template="frequency_penalty",
                    label=I18nObject(en_US="Frequency Penalty", zh_Hans="频率惩罚"),
                    type=ParameterType.FLOAT,
                    help=I18nObject(
                        en_US="Penalizes new tokens based on their existing frequency in the text.",
                        zh_Hans="根据新令牌在文本中已有的频率进行惩罚。",
                    ),
                    min=-2,
                    max=2,
                ),
                ParameterRule(
                    name="repeat_penalty",
                    label=I18nObject(en_US="Repeat Penalty", zh_Hans="重复惩罚"),
                    type=ParameterType.FLOAT,
                    help=I18nObject(
                        en_US="Sets how strongly to penalize repetitions. A higher value (e.g., 1.5) will penalize repetitions more strongly. (Default: 1.1)",
                        zh_Hans="设置对重复内容的惩罚强度。较高的值（如1.5）会更强地惩罚重复内容。（默认值：1.1）",
                    ),
                    min=0,
                    max=2,
                ),
                ParameterRule(
                    name="seed",
                    label=I18nObject(en_US="Seed", zh_Hans="随机数种子"),
                    type=ParameterType.INT,
                    help=I18nObject(
                        en_US="Sets the random number seed to use for generation. Setting this to a specific number will make the model generate the same text for the same prompt.",
                        zh_Hans="设置用于生成的随机数种子。设置为特定数字将使模型对相同提示生成相同的文本。",
                    ),
                ),
                ParameterRule(
                    name="format",
                    label=I18nObject(en_US="Format", zh_Hans="返回格式"),
                    type=ParameterType.STRING,
                    help=I18nObject(
                        en_US="Controls the response format. The only accepted value is json, which enables generic JSON output. If JSON Schema is provided below, it overrides this setting.",
                        zh_Hans="控制响应格式。目前唯一接受的值是 json，它会启用通用 JSON 输出。如果下方提供了 JSON Schema，则会覆盖此设置。",
                    ),
                    options=["json"],
                ),
                ParameterRule(
                    name="json_schema",
                    label=I18nObject(en_US="JSON Schema", zh_Hans="JSON Schema"),
                    type=ParameterType.STRING,
                    help=I18nObject(
                        en_US="Optional JSON Schema string to enforce structured output. When provided, it overrides generic JSON mode and constrains the response to the schema.",
                        zh_Hans="可选的 JSON Schema 字符串，用于强制结构化输出。提供后会覆盖通用 JSON 模式，并将响应约束到该 schema。",
                    ),
                ),
            ],
            pricing=PriceConfig(
                input=Decimal(credentials.get("input_price", 0)),
                output=Decimal(credentials.get("output_price", 0)),
                unit=Decimal(credentials.get("unit", 0)),
                currency=credentials.get("currency", "USD"),
            ),
        )
        return entity

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {
            InvokeAuthorizationError: [requests.exceptions.InvalidHeader],
            InvokeBadRequestError: [
                requests.exceptions.HTTPError,
                requests.exceptions.InvalidURL,
            ],
            InvokeRateLimitError: [requests.exceptions.RetryError],
            InvokeServerUnavailableError: [
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
            ],
            InvokeConnectionError: [
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
            ],
        }
