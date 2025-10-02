from langfuse import Langfuse
import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import time
import random
from typing import Optional, Dict, Any
from .external_service import GeminiService
from .exceptions import log_execution, handle_exceptions
from config.main import settings


class ExtractionEvaluationService:

    def __init__(self, extraction_model: str, evaluation_model: str, total_characters: int, zero_indexed: Optional[bool] = False, context: Optional[str] = None, context_upload: Optional[BytesIO] = None):
        self.extraction_model = extraction_model
        self.evaluation_model = evaluation_model
        self.context = context if context is not None else None
        self.context_upload = context_upload if context_upload is not None else None
        self.total_characters = total_characters
        self.zero_indexed = zero_indexed if zero_indexed is not None else False
        # self.langfuse_client = self._langfuse_client()
        # self.system_prompt = self.langfuse_client.get_prompt("system_prompt").prompt
        # self.extraction_prompt = self.langfuse_client.get_prompt("extraction_prompt").prompt
        # self.evaluation_prompt = self.langfuse_client.get_prompt("evaluation_prompt").prompt
        self.system_prompt = "You are a helpful and precise research assistant. Focus on extracting the requested character descriptions and corresponding states accurately from the provided text."
        self.extraction_prompt = "Here is a section of text from a phylogenetic research paper. Please extract the character descriptions and their corresponding states for character index: {character_index} Previous attempts to extract information for this character index have yielded these incorrect results:"
        self.evaluation_prompt = "Evaluate the generated answer based on the previously provided section of a phylogenetic research paper and the following user query. User Query: {extraction_prompt} Generated Answer: {extraction_reponse} Scoring Criteria: - 1-3: The generated answer is not relevant to the user query. - 4-6: The generated answer is relevant to the query but contains mistakes. A score of 4 indicates more significant errors, while 6 indicates minor errors. - 7-10: The generated answer is relevant and fully correct, accurately extracting the complete character description and all corresponding states for the requested character index. A score of 7 indicates an ok answer, while 10 indicates a perfect extraction."

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

    def _cycle(self, character_index) -> Optional[Dict[str, Any]]:
        character_index_dict = {"character_index": character_index}
        
        extraction_prompt = self.extraction_prompt.format(character_index=character_index)
        
        max_attempts = 0  # Changed from 5 to 0 for testing (1 attempt only, no retries)
        base_delay = 1
        attempt = 0
        last_error = None
        
        while attempt <= max_attempts:
            try:
                # Attempt the extraction
                extraction_response = self.gemini_service.extract(prompt=extraction_prompt)
            
                # Attempt the evaluation
                evaluation_prompt = self.evaluation_prompt.format(
                    extraction_prompt=extraction_prompt, 
                    extraction_reponse=extraction_response
                )
                evaluation_response = self.gemini_service.evaluate(prompt=evaluation_prompt)
                
                if evaluation_response["score"] >= 8:
                    response = {**character_index_dict, **extraction_response, **evaluation_response}
                    return response
                else:
                    # If score is low, we'll try again with modified prompt
                    attempt += 1
                    extraction_prompt = extraction_prompt + f"\nAttempt {attempt}: {extraction_response}"
                    
            except Exception as e:  # You should catch specific exceptions here
                last_error = e  # Store the last error
                if "429" in str(e).lower() or "exceeded your current quota" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
                    # Quota exhaustion - re-raise immediately as this is not recoverable
                    print(f"Quota exhausted for character {character_index}: {str(e)}")
                    raise
                elif "RESOURCE_EXHAUSTED" in str(e):
                    # Also catch RESOURCE_EXHAUSTED directly
                    print(f"Resource exhausted for character {character_index}: {str(e)}")
                    raise
                else:
                    # For any other error, break the loop to avoid infinite retries
                    print(f"Error in cycle for character {character_index}: {str(e)}")
                    break
        
        print(f"Failed after {max_attempts} attempts for character {character_index}")
        if last_error:
            print(f"Last error: {str(last_error)}")
        return None

    @log_execution
    @handle_exceptions
    def run_cycle(self, progress_callback=None) -> tuple[list[dict], list[int]]:
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            futures = []
            start_index = 0 if self.zero_indexed else 1
            end_index = self.total_characters
            total_tasks = end_index - start_index + 1

            # Submit all tasks
            for character_index in range(start_index, end_index + 1):
                future = executor.submit(self._cycle, character_index)
                futures.append((character_index, future))

            successful_results = []
            failed_indexes = []
            quota_exceeded = False
            
            # Process results with progress updates
            for i, (character_index, future) in enumerate(futures):
                try:
                    result = future.result()
                    if result is None:
                        failed_indexes.append(character_index)
                    else:
                        successful_results.append(result)
                except Exception as e:
                    # Check if this is a quota exhaustion error
                    error_str = str(e)
                    if "429" in error_str or "exceeded your current quota" in error_str.lower() or "RESOURCE_EXHAUSTED" in error_str:
                        print(f"Quota exceeded error caught in run_cycle: {error_str}")
                        quota_exceeded = True
                        failed_indexes.append(character_index)
                        # Don't re-raise yet, let other futures complete
                    else:
                        # For other errors, just mark as failed
                        print(f"Error processing character {character_index}: {error_str}")
                        failed_indexes.append(character_index)
                
                # Update progress if callback provided
                if progress_callback:
                    progress = (i + 1) / total_tasks
                    progress_callback(progress)
            
            # If quota was exceeded and we have no successful results, raise an error
            if quota_exceeded and len(successful_results) == 0:
                raise Exception("API quota exceeded. No characters were successfully extracted. Please check your API limits.")

            return successful_results, failed_indexes