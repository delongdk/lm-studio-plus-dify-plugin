import json
import logging
import time
from decimal import Decimal
from typing import Optional
from urllib.parse import urljoin

import numpy as np
import requests
from dify_plugin import TextEmbeddingModel
from dify_plugin.entities.model import (
    AIModelEntity,
    EmbeddingInputType,
    FetchFrom,
    I18nObject,
    ModelPropertyKey,
    ModelType,
    PriceConfig,
    PriceType,
)
from dify_plugin.entities.model.text_embedding import (
    EmbeddingUsage,
    TextEmbeddingResult,
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

logger = logging.getLogger(__name__)


class LmStudioPlusTextEmbeddingModel(TextEmbeddingModel):
    """
    Model class for LM Studio Plus text embedding model.
    Uses OpenAI-compatible /v1/embeddings endpoint.
    """

    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: Optional[str] = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        base_url = credentials.get("base_url", "http://localhost:1234")
        if base_url.endswith("/"):
            base_url = base_url.rstrip("/")
        endpoint_url = f"{base_url}/v1/embeddings"

        api_key = credentials.get("api_key", "lm-studio")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        context_size = self._get_context_size(model, credentials)
        inputs = []
        for text in texts:
            num_tokens = self._get_num_tokens_by_gpt2(text)
            if num_tokens >= context_size:
                cutoff = int(np.floor(len(text) * (context_size / num_tokens)))
                inputs.append(text[:cutoff])
            else:
                inputs.append(text)

        payload = {
            "model": model,
            "input": inputs,
        }

        response = requests.post(
            endpoint_url,
            headers=headers,
            json=payload,
            timeout=(10, 300),
        )
        response.raise_for_status()
        response_data = response.json()

        embeddings = [item["embedding"] for item in response_data.get("data", [])]

        usage_data = response_data.get("usage", {})
        used_tokens = usage_data.get("total_tokens", 0)
        if not used_tokens:
            used_tokens = sum(self.get_num_tokens(model, credentials, inputs))

        usage = self._calc_response_usage(
            model=model, credentials=credentials, tokens=used_tokens
        )

        return TextEmbeddingResult(embeddings=embeddings, usage=usage, model=model)

    def get_num_tokens(
        self, model: str, credentials: dict, texts: list[str]
    ) -> list[int]:
        return [self._get_num_tokens_by_gpt2(text) for text in texts]

    def validate_credentials(self, model: str, credentials: dict) -> None:
        try:
            self._invoke(model=model, credentials=credentials, texts=["ping"])
        except InvokeError as ex:
            raise CredentialsValidateFailedError(
                f"An error occurred during credentials validation: {ex.description}"
            )
        except requests.HTTPError as ex:
            raise CredentialsValidateFailedError(
                f"An error occurred during credentials validation: status code {ex.response.status_code}: {ex.response.text}"
            )
        except Exception as ex:
            raise CredentialsValidateFailedError(
                f"An error occurred during credentials validation: {str(ex)}"
            )

    def get_customizable_model_schema(
        self, model: str, credentials: dict
    ) -> AIModelEntity:
        entity = AIModelEntity(
            model=model,
            label=I18nObject(en_US=model),
            model_type=ModelType.TEXT_EMBEDDING,
            fetch_from=FetchFrom.CUSTOMIZABLE_MODEL,
            model_properties={
                ModelPropertyKey.CONTEXT_SIZE: int(
                    credentials.get("context_size", 512)
                ),
                ModelPropertyKey.MAX_CHUNKS: 1,
            },
            parameter_rules=[],
            pricing=PriceConfig(
                input=Decimal(credentials.get("input_price", 0)),
                unit=Decimal(credentials.get("unit", 0)),
                currency=credentials.get("currency", "USD"),
            ),
        )
        return entity

    def _calc_response_usage(
        self, model: str, credentials: dict, tokens: int
    ) -> EmbeddingUsage:
        input_price_info = self.get_price(
            model=model,
            credentials=credentials,
            price_type=PriceType.INPUT,
            tokens=tokens,
        )
        usage = EmbeddingUsage(
            tokens=tokens,
            total_tokens=tokens,
            unit_price=input_price_info.unit_price,
            price_unit=input_price_info.unit,
            total_price=input_price_info.total_amount,
            currency=input_price_info.currency,
            latency=time.perf_counter() - self.started_at,
        )
        return usage

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
