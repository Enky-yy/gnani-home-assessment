import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable

from app.config import settings

logger = logging.getLogger(__name__)


class AudioSummaryOutput(BaseModel):
    """Pydantic schema for structured LangChain output."""
    tldr: str = Field(description="A clear, concise 2-3 sentence executive summary of the entire audio note.")
    key_points: List[str] = Field(default_factory=list, description="Key discussion takeaways and crucial insights.")
    action_items: List[str] = Field(default_factory=list, description="Specific follow-up tasks, next steps, or deadlines.")
    sentiment: str = Field(default="Neutral", description="Tone: Positive, Constructive, Urgent, Neutral, Collaborative, Inquisitive")


class SummarizerService:
    """Unified LangChain summarization service supporting Gemini, Groq, and OpenAI via LCEL chains."""

    def __init__(self):
        self.parser = JsonOutputParser(pydantic_object=AudioSummaryOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert executive assistant and speech intelligence analyst.\n"
                "Analyze the provided speech-to-text transcript and extract a structured summary.\n"
                "{format_instructions}"
            ),
            (
                "human",
                "TRANSCRIPT TO ANALYZE:\n\"\"\"\n{transcript}\n\"\"\""
            )
        ]).partial(format_instructions=self.parser.get_format_instructions())

        # Build active LLM and chain
        self.llm, self.model_name = self._init_chat_model()
        self.chain = self._build_chain()

    def _init_chat_model(self) -> Tuple[Optional[Any], Optional[str]]:
        """Instantiate the configured LangChain chat model."""
        provider = settings.LLM_PROVIDER.lower()

        # 1. Primary configured provider
        if provider == "gemini" and settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return (
                ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL,
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.2,
                ),
                f"gemini/{settings.GEMINI_MODEL}",
            )

        if provider == "groq" and settings.GROQ_API_KEY:
            from langchain_groq import ChatGroq
            return (
                ChatGroq(
                    model=settings.GROQ_MODEL,
                    api_key=settings.GROQ_API_KEY,
                    temperature=0.2,
                ),
                f"groq/{settings.GROQ_MODEL}",
            )

        if provider == "openai" and settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return (
                ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    api_key=settings.OPENAI_API_KEY,
                    temperature=0.2,
                ),
                f"openai/{settings.OPENAI_MODEL}",
            )

        # 2. Fallback to any available provider key
        if settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return (
                ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL,
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.2,
                ),
                f"gemini/{settings.GEMINI_MODEL}",
            )
        elif settings.GROQ_API_KEY:
            from langchain_groq import ChatGroq
            return (
                ChatGroq(
                    model=settings.GROQ_MODEL,
                    api_key=settings.GROQ_API_KEY,
                    temperature=0.2,
                ),
                f"groq/{settings.GROQ_MODEL}",
            )
        elif settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return (
                ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    api_key=settings.OPENAI_API_KEY,
                    temperature=0.2,
                ),
                f"openai/{settings.OPENAI_MODEL}",
            )

        logger.info("No LLM API keys configured. Using local extractive engine.")
        return None, None

    def _build_chain(self) -> Optional[Runnable]:
        """Construct the LangChain LCEL chain: Prompt | LLM | Parser."""
        if not self.llm:
            return None

        try:
            # Prefer with_structured_output when supported
            structured_llm = self.llm.with_structured_output(AudioSummaryOutput)
            chain = self.prompt | structured_llm
            logger.info(f"Initialized LangChain structured output chain with model: {self.model_name}")
            return chain
        except Exception as e:
            logger.info(f"Using standard Prompt | LLM | JsonOutputParser chain ({e})")
            return self.prompt | self.llm | self.parser

    async def summarize(self, transcript: str) -> Dict[str, Any]:
        """Run the LangChain chain to extract structured audio notes summary."""
        if not transcript or not transcript.strip():
            return {
                "tldr": "No speech detected in audio.",
                "key_points": [],
                "action_items": [],
                "sentiment": "Neutral",
                "model_used": "none",
            }

        # Execute LangChain chain if active
        if self.chain:
            try:
                logger.info(f"Invoking LangChain summarization chain with model: {self.model_name}")
                result = await self.chain.ainvoke({"transcript": transcript})

                # Handle output whether Pydantic object or dict
                if isinstance(result, AudioSummaryOutput):
                    return {
                        "tldr": result.tldr,
                        "key_points": result.key_points,
                        "action_items": result.action_items,
                        "sentiment": result.sentiment,
                        "model_used": self.model_name,
                    }
                elif isinstance(result, dict):
                    return {
                        "tldr": result.get("tldr", "Summary extracted."),
                        "key_points": result.get("key_points", []),
                        "action_items": result.get("action_items", []),
                        "sentiment": result.get("sentiment", "Neutral"),
                        "model_used": self.model_name,
                    }
            except Exception as e:
                logger.error(f"LangChain chain execution failed: {e}. Falling back to extractive engine.")

        # Offline / zero-key fallback
        return self._extractive_summary_fallback(transcript)

    def _extractive_summary_fallback(self, transcript: str) -> Dict[str, Any]:
        """Heuristic rule-based extractive summary for zero-cloud and test runs."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", transcript) if len(s.strip()) > 10]
        
        tldr = " ".join(sentences[:2]) + "." if sentences else transcript[:150]
        key_points = sentences[1:5] if len(sentences) > 2 else [sentences[0]] if sentences else ["Voice note transcribed successfully."]
        
        action_keywords = ["todo", "action", "next step", "need to", "must", "follow up", "will", "prepare"]
        action_items = []
        for s in sentences:
            if any(k in s.lower() for k in action_keywords):
                action_items.append(s.strip().capitalize() + ".")
                if len(action_items) >= 3:
                    break

        return {
            "tldr": tldr,
            "key_points": key_points,
            "action_items": action_items if action_items else ["Review transcribed notes and assign owners."],
            "sentiment": "Collaborative",
            "model_used": "langchain-extractive-fallback",
        }
