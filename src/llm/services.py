from langfuse import Langfuse
import os
from io import BytesIO
from pathlib import Path
import streamlit as st
import logging
import yaml
from typing import Optional, Dict, Any
from .external_service import GeminiService
from .exceptions import log_execution, handle_exceptions
from config.main import settings

# Load prompts from external YAML config
_PROMPTS_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts.yaml"
with open(_PROMPTS_PATH, "r", encoding="utf-8") as _f:
    _PROMPTS = yaml.safe_load(_f)

logger = logging.getLogger(__name__)


class ExtractionEvaluationService:

    def __init__(self, extraction_model: str, evaluation_model: str, total_characters: int, zero_indexed: Optional[bool] = False, context: Optional[str] = None, context_upload: Optional[BytesIO] = None):
        self.extraction_model = extraction_model
        self.evaluation_model = evaluation_model
        self.context = context if context is not None else None
        self.context_upload = context_upload if context_upload is not None else None
        self.total_characters = total_characters
        self.zero_indexed = zero_indexed if zero_indexed is not None else False
        # Prompts loaded from src/config/prompts.yaml
        # To use Langfuse instead, uncomment the lines below:
        # self.langfuse_client = self._langfuse_client()
        # self.system_prompt = self.langfuse_client.get_prompt("system_prompt").prompt
        # self.extraction_prompt = self.langfuse_client.get_prompt("extraction_prompt").prompt
        # self.evaluation_prompt = self.langfuse_client.get_prompt("evaluation_prompt").prompt
        self.system_prompt = _PROMPTS["system_prompt"]
        self.extraction_prompt = _PROMPTS["extraction_prompt"]
        self.evaluation_prompt = _PROMPTS["evaluation_prompt"]

        self.gemini_service = self._gemini_service()

    @log_execution
    @handle_exceptions
    def _langfuse_client(self) -> Langfuse:

        langfuse_client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY") or st.secrets["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.getenv("LANGFUSE_SECRET_KEY") or st.secrets["LANGFUSE_SECRET_KEY"],
            host=os.getenv("LANGFUSE_HOST") or st.secrets["LANGFUSE_HOST"],
        )
    
        return langfuse_client

    @log_execution
    @handle_exceptions   
    def _gemini_service(self):
        
        if self.context is not None:
            gemini_service = GeminiService(extraction_model=self.extraction_model, evaluation_model=self.evaluation_model, system_prompt=self.system_prompt, context=self.context)
            return gemini_service

        elif self.context_upload is not None:
            gemini_service = GeminiService(extraction_model=self.extraction_model, evaluation_model=self.evaluation_model, system_prompt=self.system_prompt, context_upload=self.context_upload)
            return gemini_service

    @log_execution
    @handle_exceptions
    def run_cycle(self, progress_callback=None) -> tuple[list[dict], list[int]]:
        """
        Batch extraction: one LLM call extracts ALL characters, then one
        evaluation call validates the result.  Returns (results, failed_indexes).
        """
        logger.info(f"🚀 Starting BATCH extraction (up to {self.total_characters} characters)")
        logger.info(f"   Extraction model: {self.extraction_model}")
        logger.info(f"   Evaluation model: {self.evaluation_model}")

        # --- Step 1: Single batch extraction call ---
        extraction_prompt = self.extraction_prompt.format(
            total_characters=self.total_characters
        )

        if progress_callback:
            progress_callback(0.1)  # 10% – starting extraction

        try:
            characters = self.gemini_service.extract_batch(prompt=extraction_prompt)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                raise Exception("API quota exceeded during extraction. Please check your API limits.")
            raise

        if not characters:
            logger.warning("⚠ Batch extraction returned 0 characters")
            return [], []

        logger.info(f"✅ Batch extraction returned {len(characters)} characters")

        if progress_callback:
            progress_callback(0.6)  # 60% – extraction done

        # --- Step 2: Single batch evaluation call ---
        evaluation_prompt = self.evaluation_prompt.format(
            extraction_response=characters
        )

        evaluation_score = None
        try:
            evaluation_response = self.gemini_service.evaluate(prompt=evaluation_prompt)
            evaluation_score = evaluation_response.get("score", 0)
            logger.info(f"✅ Batch evaluation score: {evaluation_score}/10 – {evaluation_response.get('justification', '')[:120]}")
        except Exception as e:
            logger.warning(f"⚠ Evaluation call failed, keeping extraction results anyway: {e}")
            evaluation_score = None  # Treat as pass if evaluation fails

        if progress_callback:
            progress_callback(0.9)  # 90% – evaluation done

        # --- Step 3: Build results list (same shape the rest of the pipeline expects) ---
        start_index = 0 if self.zero_indexed else 1
        successful_results = []
        for i, char_data in enumerate(characters):
            result = {
                "character_index": start_index + i,
                "character": char_data.get("character", ""),
                "states": char_data.get("states", []),
                "score": evaluation_score,
                "justification": evaluation_response.get("justification", "") if evaluation_score is not None else "evaluation skipped",
            }
            successful_results.append(result)

        failed_indexes = []  # Batch mode: no per-character failures

        if progress_callback:
            progress_callback(1.0)

        logger.info(f"🏁 Batch complete: {len(successful_results)} characters extracted, evaluation score {evaluation_score}")
        return successful_results, failed_indexes
    
    def get_token_usage(self) -> dict:
        """Return accumulated token usage from the underlying GeminiService."""
        if self.gemini_service:
            return dict(self.gemini_service.token_usage)
        return {}