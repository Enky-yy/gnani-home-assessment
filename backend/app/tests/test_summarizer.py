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
