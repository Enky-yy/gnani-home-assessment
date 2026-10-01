import pytest
from app.services.summarizer import SummarizerService, AudioSummaryOutput


@pytest.mark.asyncio
async def test_summarizer_chain_structure():
    svc = SummarizerService()
    assert svc.parser is not None
    assert svc.prompt is not None

    sample_transcript = (
        "We held our weekly voice engineering sync today. "
        "The team agreed to deploy the new LangChain summarization chain to production. "
        "Action item: Rahul will verify the Docker compose setup on AWS EC2 by Friday."
    )

    result = await svc.summarize(sample_transcript)
    assert "tldr" in result
    assert "key_points" in result
    assert "action_items" in result
    assert "sentiment" in result
    assert len(result["tldr"]) > 0
    assert len(result["key_points"]) > 0


@pytest.mark.asyncio
async def test_summarizer_empty_transcript():
    svc = SummarizerService()
    result = await svc.summarize("")
    assert result["tldr"] == "No speech detected in audio."
    assert result["key_points"] == []
    assert result["action_items"] == []


class _FakeChain:
    def __init__(self, payload):
        self.payload = payload

    async def ainvoke(self, _input):
        return self.payload


@pytest.mark.asyncio
async def test_summarizer_fails_over_to_next_provider(monkeypatch):
    """Dead primary key must not pin us to extractive when a backup works."""
    import unittest.mock as mock

    svc = SummarizerService()
    monkeypatch.setattr(svc, "provider_order", ["dead", "alive"])
    monkeypatch.setattr(svc, "_build_llm", lambda p: (object(), f"{p}/model"))
    good = {"tldr": "Real LLM summary.", "key_points": ["kp"], "action_items": [], "sentiment": "Positive"}
    monkeypatch.setattr(
        svc, "_build_chain", mock.Mock(side_effect=[Exception("401 Unauthorized"), _FakeChain(good)])
    )
    result = await svc.summarize("Some transcript with enough words to summarize properly here.")
    assert result["tldr"] == "Real LLM summary."
    assert result["model_used"] == "alive/model"


@pytest.mark.asyncio
async def test_summarizer_all_providers_down_uses_extractive(monkeypatch):
    import unittest.mock as mock

    svc = SummarizerService()
    monkeypatch.setattr(svc, "provider_order", ["dead1", "dead2"])
    monkeypatch.setattr(svc, "_build_llm", lambda p: (object(), f"{p}/model"))
    monkeypatch.setattr(svc, "_build_chain", mock.Mock(side_effect=Exception("boom")))
    result = await svc.summarize("First sentence here. Second sentence here for the fallback engine.")
    assert result["model_used"] == "langchain-extractive-fallback"
    assert result["tldr"]


def test_placeholder_keys_are_not_configured():
    from app.config import is_configured_key

    assert is_configured_key("your_groq_api_key_here") is False
    assert is_configured_key("YOUR_OPENAI_KEY_HERE") is False
    assert is_configured_key("") is False
    assert is_configured_key(None) is False
    assert is_configured_key("gsk_realkey123") is True


def test_provider_order_ignores_placeholders(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "gsk_realkey123")
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "your_openai_api_key_here")
    svc = SummarizerService()
    assert svc.provider_order == ["groq"]
