import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from open_webui.routers.gatewayz import (
    extract_top_models_by_provider,
    TOP_MODEL_PROVIDERS,
    TOP_MODELS_PER_PROVIDER,
)


class TestExtractTopModelsByProvider:
    """Tests for the extract_top_models_by_provider function"""

    def test_extract_top_models_empty_rankings(self):
        """Should return empty list for empty rankings"""
        result = extract_top_models_by_provider([], TOP_MODEL_PROVIDERS, 3)
        assert result == []

    def test_extract_top_models_none_rankings(self):
        """Should return empty list for None rankings"""
        result = extract_top_models_by_provider(None, TOP_MODEL_PROVIDERS, 3)
        assert result == []

    def test_extract_top_models_dict_with_data(self):
        """Should handle rankings wrapped in dict with data key"""
        rankings = {
            "data": [
                {"id": "gpt-4", "provider": "openai"},
                {"id": "claude-3", "provider": "anthropic"},
            ]
        }
        result = extract_top_models_by_provider(rankings, ["openai", "anthropic"], 3)
        assert "gpt-4" in result
        assert "claude-3" in result

    def test_extract_top_models_list_format(self):
        """Should handle rankings as a direct list"""
        rankings = [
            {"id": "gpt-4", "provider": "openai"},
            {"id": "gpt-4-turbo", "provider": "openai"},
            {"id": "gpt-3.5-turbo", "provider": "openai"},
            {"id": "gpt-4o", "provider": "openai"},
            {"id": "claude-3-opus", "provider": "anthropic"},
            {"id": "claude-3-sonnet", "provider": "anthropic"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai", "anthropic"], 3)

        # Should have top 3 from openai and top 3 from anthropic
        openai_models = [m for m in result if "gpt" in m]
        anthropic_models = [m for m in result if "claude" in m]

        assert len(openai_models) == 3  # Top 3 OpenAI
        assert len(anthropic_models) == 2  # Only 2 Anthropic models available

    def test_extract_top_models_uses_model_id_field(self):
        """Should extract from model_id field when present"""
        rankings = [
            {"model_id": "gpt-4", "provider": "openai"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai"], 3)
        assert "gpt-4" in result

    def test_extract_top_models_uses_name_field(self):
        """Should fall back to name field when id not present"""
        rankings = [
            {"name": "gpt-4", "provider": "openai"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai"], 3)
        assert "gpt-4" in result

    def test_extract_top_models_infers_provider_from_id(self):
        """Should infer provider from model ID when provider field missing"""
        rankings = [
            {"id": "openai/gpt-4"},
            {"id": "anthropic/claude-3"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai", "anthropic"], 3)
        assert "openai/gpt-4" in result
        assert "anthropic/claude-3" in result

    def test_extract_top_models_uses_owned_by_field(self):
        """Should use owned_by field for provider"""
        rankings = [
            {"id": "gpt-4", "owned_by": "openai"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai"], 3)
        assert "gpt-4" in result

    def test_extract_top_models_respects_top_n_limit(self):
        """Should only return top N models per provider"""
        rankings = [
            {"id": "gpt-4", "provider": "openai"},
            {"id": "gpt-4-turbo", "provider": "openai"},
            {"id": "gpt-3.5", "provider": "openai"},
            {"id": "gpt-4o", "provider": "openai"},
            {"id": "gpt-4o-mini", "provider": "openai"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai"], 2)
        assert len(result) == 2
        # Should be first 2 in order
        assert "gpt-4" in result
        assert "gpt-4-turbo" in result

    def test_extract_top_models_case_insensitive_provider(self):
        """Should match providers case-insensitively"""
        rankings = [
            {"id": "gpt-4", "provider": "OpenAI"},
            {"id": "claude-3", "provider": "ANTHROPIC"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai", "anthropic"], 3)
        assert "gpt-4" in result
        assert "claude-3" in result

    def test_extract_top_models_skips_non_dict_items(self):
        """Should skip non-dict items in rankings"""
        rankings = [
            {"id": "gpt-4", "provider": "openai"},
            "invalid_item",
            None,
            {"id": "claude-3", "provider": "anthropic"},
        ]
        result = extract_top_models_by_provider(rankings, ["openai", "anthropic"], 3)
        assert "gpt-4" in result
        assert "claude-3" in result

    def test_extract_top_models_all_four_providers(self):
        """Should extract from all four target providers"""
        rankings = [
            {"id": "gpt-4", "provider": "openai"},
            {"id": "gpt-4-turbo", "provider": "openai"},
            {"id": "gpt-3.5", "provider": "openai"},
            {"id": "claude-3-opus", "provider": "anthropic"},
            {"id": "claude-3-sonnet", "provider": "anthropic"},
            {"id": "claude-3-haiku", "provider": "anthropic"},
            {"id": "gemini-pro", "provider": "google"},
            {"id": "gemini-ultra", "provider": "google"},
            {"id": "gemini-nano", "provider": "google"},
            {"id": "grok-1", "provider": "xai"},
            {"id": "grok-2", "provider": "xai"},
            {"id": "grok-3", "provider": "xai"},
        ]
        result = extract_top_models_by_provider(
            rankings, TOP_MODEL_PROVIDERS, TOP_MODELS_PER_PROVIDER
        )

        # Should have 12 models total (3 per provider × 4 providers)
        assert len(result) == 12

        # Verify each provider has 3 models
        openai_count = sum(1 for m in result if "gpt" in m)
        anthropic_count = sum(1 for m in result if "claude" in m)
        google_count = sum(1 for m in result if "gemini" in m)
        xai_count = sum(1 for m in result if "grok" in m)

        assert openai_count == 3
        assert anthropic_count == 3
        assert google_count == 3
        assert xai_count == 3

    def test_extract_top_models_no_duplicates(self):
        """Should not include duplicate model IDs"""
        rankings = [
            {"id": "gpt-4", "provider": "openai"},
            {"id": "gpt-4", "provider": "openai"},  # duplicate
        ]
        result = extract_top_models_by_provider(rankings, ["openai"], 3)
        assert result.count("gpt-4") == 1


class TestTopModelProviders:
    """Tests for default configuration constants"""

    def test_default_providers(self):
        """Should have the four expected providers"""
        assert "openai" in TOP_MODEL_PROVIDERS
        assert "anthropic" in TOP_MODEL_PROVIDERS
        assert "google" in TOP_MODEL_PROVIDERS
        assert "xai" in TOP_MODEL_PROVIDERS
        assert len(TOP_MODEL_PROVIDERS) == 4

    def test_default_top_n(self):
        """Should default to top 3 models per provider"""
        assert TOP_MODELS_PER_PROVIDER == 3
