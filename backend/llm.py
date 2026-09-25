"""
Shared LLM helpers: client creation for OpenAI or any OpenAI-compatible
provider (e.g. Volcano Engine Ark), and Structured Outputs.
"""
import json
import logging
from typing import Dict, List, Optional, Set, Tuple, Type, TypeVar

from openai import BadRequestError, OpenAI
from openai.lib._pydantic import to_strict_json_schema
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from pydantic import BaseModel

DEFAULT_LLM_MODEL = "gpt-4o"

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger("llm")

# (base_url, model) pairs whose provider rejected json_schema; skip straight to JSON mode
_json_schema_unsupported: Set[Tuple[str, str]] = set()


def create_llm_client(api_key: str, base_url: Optional[str] = None) -> OpenAI:
    """
    Create a chat client; base_url switches to an OpenAI-compatible provider.
    Low-tier API keys hit tokens-per-minute limits quickly (an agent search
    sends several large requests), so rate-limited calls are retried with the
    SDK's exponential backoff more times than its default of 2.
    """
    return OpenAI(api_key=api_key, base_url=base_url or None, max_retries=6)


def json_schema_format(schema: Type[BaseModel]) -> Dict:
    """response_format for Structured Outputs: the model must return JSON matching `schema`."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": to_strict_json_schema(schema),
            "strict": True,
        },
    }


def create_with_schema(
    client: OpenAI,
    model: str,
    messages: List[Dict],
    schema: Type[BaseModel],
    **kwargs,
) -> ChatCompletion:
    """
    chat.completions.create with Structured Outputs; works together with tools=...

    Some OpenAI-compatible providers only support JSON mode. If the provider
    rejects response_format, retry with {"type": "json_object"} plus the schema
    in the prompt (and remember that for this provider/model). Other 400s are
    raised unchanged.
    """
    key = (str(client.base_url), model)
    if key not in _json_schema_unsupported:
        try:
            return client.chat.completions.create(
                model=model, messages=messages, response_format=json_schema_format(schema), **kwargs
            )
        except BadRequestError as e:
            if "response_format" not in str(e) and "json_schema" not in str(e):
                raise
            logger.warning(f"{model} rejected Structured Outputs, falling back to JSON mode: {e}")
            _json_schema_unsupported.add(key)

    schema_hint = {
        "role": "system",
        "content": "When you give your final reply, reply with one JSON object matching this JSON Schema:\n"
                   + json.dumps(to_strict_json_schema(schema)),
    }
    return client.chat.completions.create(
        model=model, messages=messages + [schema_hint], response_format={"type": "json_object"}, **kwargs
    )


def parse_reply(message: ChatCompletionMessage, schema: Type[T]) -> T:
    """Validate an assistant reply against `schema` (raises ValueError / ValidationError)."""
    if getattr(message, "refusal", None):
        raise ValueError(f"Model refused the request: {message.refusal}")
    content = (message.content or "").strip()
    if content.startswith("```"):  # JSON-mode providers sometimes wrap output in a code fence
        content = content.strip("`").removeprefix("json").strip()
    return schema.model_validate_json(content)


def structured_completion(
    client: OpenAI,
    model: str,
    messages: List[Dict],
    schema: Type[T],
    **kwargs,
) -> T:
    """Run a chat completion whose reply is validated against a Pydantic schema."""
    response = create_with_schema(client, model, messages, schema, **kwargs)
    return parse_reply(response.choices[0].message, schema)
