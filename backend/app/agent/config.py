"""Bedrock model configuration for the medical data analysis Agent.

The actual ``BedrockModel`` is built lazily inside :func:`build_bedrock_model`
so that importing this module does not require the ``strands`` SDK. The model
parameters themselves are exposed as a plain, dependency-free dataclass
(:class:`ModelParameters`) and via :func:`get_model_parameters`, allowing tests
to assert on the design defaults (model id, region, temperature, max tokens)
without the heavy AI dependencies installed.

Design defaults (from design.md → "Agent 设计"):
    model_id    = "anthropic.claude-sonnet-4-20250514-v1:0"
    region_name = "us-west-2"
    temperature = 0.3
    max_tokens  = 4096

Requirements: 3.1-3.8, 9.5-9.9
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.config import settings


@dataclass(frozen=True)
class ModelParameters:
    """Plain, SDK-free description of the Bedrock model parameters.

    Attributes:
        model_id: Bedrock model identifier (Claude Sonnet).
        region_name: AWS region hosting the Bedrock endpoint.
        temperature: Sampling temperature (lower = more deterministic).
        max_tokens: Maximum number of tokens to generate per response.
    """

    model_id: str
    region_name: str
    temperature: float
    max_tokens: int


def get_model_parameters() -> ModelParameters:
    """Return the Bedrock model parameters resolved from application settings.

    These values default to the design specification but can be overridden via
    ``APP_BEDROCK_MODEL_ID`` / ``APP_BEDROCK_REGION`` / ``APP_AGENT_TEMPERATURE``
    / ``APP_AGENT_MAX_TOKENS`` environment variables.

    Returns:
        A :class:`ModelParameters` instance. No ``strands``/``mcp`` import is
        required to call this function.
    """
    return ModelParameters(
        model_id=settings.bedrock_model_id,
        region_name=settings.bedrock_region,
        temperature=settings.agent_temperature,
        max_tokens=settings.agent_max_tokens,
    )


def build_bedrock_model():
    """Build and return a configured Strands ``BedrockModel``.

    ``strands`` is imported lazily here so that importing this module (and
    running the pure config/prompt unit tests) does not require the Strands SDK
    to be installed.

    Returns:
        A configured ``strands.models.BedrockModel`` instance.

    Raises:
        RuntimeError: If the ``strands`` package is not installed.
    """
    try:
        from strands.models import BedrockModel  # lazy import
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "The 'strands-agents' package is required to build the Bedrock model. "
            "Install it with 'pip install strands-agents'."
        ) from exc

    params = get_model_parameters()
    return BedrockModel(
        model_id=params.model_id,
        region_name=params.region_name,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
    )
