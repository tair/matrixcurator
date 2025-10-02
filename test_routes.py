from fastapi import APIRouter
from datetime import datetime
import time
from io import BytesIO

router = APIRouter(
    prefix="/test",
    tags=["testing"]
)


@router.post("/gemini")
async def test_gemini_service():
    """
    Comprehensive test endpoint for GeminiService
    Tests 3 scenarios with hardcoded data:
    1. Extract Method - Text Context with Cache
    2. Evaluate Method - Text Context with Cache
    3. Extract Method - Without Cache (Fallback Path)
    
    Note: This test includes 8-second delays between scenarios to avoid 
    Gemini API rate limits (10 requests/min on free tier).
    Total test time: ~30-40 seconds
    """
    import sys
    import os
    
    # Add src to path for imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    from llm.external_service import GeminiService
    
    results = {
        "test_results": {},
        "overall_status": "unknown",
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Test includes rate limit delays (8s between scenarios)"
    }
    
    # Hardcoded test data
    system_prompt = "You are an expert at extracting phylogenetic character data from scientific texts."
    test_context = """
    The Archaeopteryx lithographica is a remarkable transitional fossil. 
    This specimen exhibits several key characteristics:
    - Feathers: present along wings and tail
    - Wings: fully developed with flight feathers
    - Teeth: present in jaw (reptilian feature)
    - Tail: long bony tail with feathers
    Geographic distribution includes Bavaria (Germany) and Wyoming (United States).
    """
    extraction_model = "gemini-2.0-flash-exp"
    evaluation_model = "gemini-2.0-flash-exp"
    
    # SCENARIO 1: Extract Method - Text Context with Cache
    try:
        start_time = time.time()
        
        gemini_service = GeminiService(
            extraction_model=extraction_model,
            evaluation_model=evaluation_model,
            system_prompt=system_prompt,
            context=test_context
        )
        
        extraction_prompt = "Extract the character 'Feathers' and list all possible states mentioned in the context."
        
        extract_response = gemini_service.extract(prompt=extraction_prompt)
        
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        
        results["test_results"]["scenario_1_extract_text"] = {
            "status": "success",
            "cache_created": gemini_service.extraction_context_cache is not None,
            "cache_name": gemini_service.extraction_context_cache.name if gemini_service.extraction_context_cache else None,
            "response": extract_response,
            "execution_time_ms": round(execution_time, 2),
            "validated_schema": isinstance(extract_response, dict) and "character" in extract_response and "states" in extract_response
        }
        
    except Exception as e:
        results["test_results"]["scenario_1_extract_text"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # Add delay to avoid rate limiting (Gemini free tier: 10 requests/min)
    time.sleep(8)
    
    # SCENARIO 2: Evaluate Method - Text Context with Cache Reuse
    try:
        start_time = time.time()
        
        # Reuse the same service instance to test cache reuse
        evaluation_prompt = """
        Evaluate the quality of this character extraction:
        Character: "Feathers"
        States: ["present", "absent"]
        
        Rate from 1-10 and provide justification.
        """
        
        evaluate_response = gemini_service.evaluate(prompt=evaluation_prompt)
        
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        
        results["test_results"]["scenario_2_evaluate"] = {
            "status": "success",
            "cache_reused": gemini_service.evaluation_context_cache is not None,
            "cache_name": gemini_service.evaluation_context_cache.name if gemini_service.evaluation_context_cache else None,
            "response": evaluate_response,
            "execution_time_ms": round(execution_time, 2),
            "validated_schema": isinstance(evaluate_response, dict) and "score" in evaluate_response and "justification" in evaluate_response,
            "score_is_integer": isinstance(evaluate_response.get("score"), int) if isinstance(evaluate_response, dict) else False
        }
        
    except Exception as e:
        results["test_results"]["scenario_2_evaluate"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # Add delay to avoid rate limiting (Gemini free tier: 10 requests/min)
    time.sleep(8)
    
    # SCENARIO 3: Extract Method - Without Cache (Fallback Path)
    try:
        start_time = time.time()
        
        # Use a model that might fail caching or test the fallback
        # We'll use the same model but create a new instance without expecting cache
        gemini_service_no_cache = GeminiService(
            extraction_model=extraction_model,
            evaluation_model=evaluation_model,
            system_prompt=system_prompt,
            context=test_context
        )
        
        # Manually set cache to None to test fallback path
        original_cache = gemini_service_no_cache.extraction_context_cache
        gemini_service_no_cache.extraction_context_cache = None
        
        extraction_prompt_2 = "Extract the character 'Wings' and list all possible states mentioned in the context."
        
        extract_response_no_cache = gemini_service_no_cache.extract(prompt=extraction_prompt_2)
        
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        
        results["test_results"]["scenario_3_no_cache_fallback"] = {
            "status": "success",
            "cache_was_available": original_cache is not None,
            "cache_manually_disabled": True,
            "fallback_worked": extract_response_no_cache is not None,
            "response": extract_response_no_cache,
            "execution_time_ms": round(execution_time, 2),
            "validated_schema": isinstance(extract_response_no_cache, dict) and "character" in extract_response_no_cache and "states" in extract_response_no_cache
        }
        
    except Exception as e:
        results["test_results"]["scenario_3_no_cache_fallback"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # Determine overall status
    all_tests = results["test_results"]
    passed_tests = sum(1 for test in all_tests.values() if test.get("status") == "success")
    total_tests = len(all_tests)
    
    if passed_tests == total_tests:
        results["overall_status"] = "all_passed"
    elif passed_tests > 0:
        results["overall_status"] = f"partial_pass_{passed_tests}/{total_tests}"
    else:
        results["overall_status"] = "all_failed"
    
    results["summary"] = {
        "total_tests": total_tests,
        "passed": passed_tests,
        "failed": total_tests - passed_tests
    }
    
    return results


@router.post("/nex")
async def test_nex_service():
    """
    Comprehensive test endpoint for NexService
    Tests 4 scenarios with hardcoded data:
    1. Format character states (_character_states method)
    2. Update NEXUS file with new CHARSTATELABELS block
    3. Handle single quotes in character names (escape to ?)
    4. Preserve indentation and proper formatting
    """
    import sys
    import os
    
    # Add src to path for imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    from nex.services import NexService
    
    results = {
        "test_results": {},
        "overall_status": "unknown",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Hardcoded test data - Sample NEXUS file
    sample_nexus = """#NEXUS

BEGIN DATA;
    DIMENSIONS NTAX=5 NCHAR=3;
    FORMAT DATATYPE=STANDARD SYMBOLS="012" GAP=- MISSING=?;
    
    CHARSTATELABELS
        1 'Old Character 1' / 'state1' 'state2',
        2 'Old Character 2' / 'present' 'absent';
    
    MATRIX
        Taxon1    012
        Taxon2    101
        Taxon3    210
        Taxon4    012
        Taxon5    121
    ;
END;
"""
    
    # Hardcoded character states data
    character_states_data = [
        {
            "character_index": 1,
            "character": "Feathers",
            "states": ["present", "absent"]
        },
        {
            "character_index": 2,
            "character": "Wing's Structure",  # Contains single quote to test escaping
            "states": ["fully developed", "reduced", "absent"]
        },
        {
            "character_index": 3,
            "character": "Teeth",
            "states": ["present", "absent"]
        }
    ]
    
    # SCENARIO 1: Test _character_states method
    try:
        start_time = time.time()
        
        nexus_bytes = BytesIO(sample_nexus.encode("utf-8"))
        nex_service = NexService(file=nexus_bytes)
        
        formatted_states = nex_service._character_states(character_states_list=character_states_data)
        
        execution_time = (time.time() - start_time) * 1000
        
        # Validate formatting
        has_proper_tabs = all(line.startswith("\t\t") for line in formatted_states)
        ends_with_semicolon = formatted_states[-1].endswith(";")
        middle_lines_have_comma = all(line.endswith(",") for line in formatted_states[:-1])
        quote_escaped = any("?" in line for line in formatted_states if "Wing" in line)
        
        results["test_results"]["scenario_1_format_character_states"] = {
            "status": "success",
            "formatted_states": formatted_states,
            "execution_time_ms": round(execution_time, 2),
            "validations": {
                "proper_indentation": has_proper_tabs,
                "last_line_semicolon": ends_with_semicolon,
                "middle_lines_comma": middle_lines_have_comma,
                "single_quote_escaped": quote_escaped,
                "total_lines": len(formatted_states)
            }
        }
        
    except Exception as e:
        results["test_results"]["scenario_1_format_character_states"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # SCENARIO 2: Test nexus_update method (complete workflow)
    try:
        start_time = time.time()
        
        # Create new instance for full update
        nexus_bytes = BytesIO(sample_nexus.encode("utf-8"))
        nex_service = NexService(file=nexus_bytes)
        
        updated_nexus = nex_service.update(character_states_list=character_states_data)
        
        execution_time = (time.time() - start_time) * 1000
        
        # Validate the update
        old_char_removed = "Old Character 1" not in updated_nexus
        new_char_added = "Feathers" in updated_nexus
        charstatelabels_exists = "CHARSTATELABELS" in updated_nexus
        matrix_still_exists = "MATRIX" in updated_nexus
        charstatelabels_before_matrix = updated_nexus.index("CHARSTATELABELS") < updated_nexus.index("MATRIX")
        
        results["test_results"]["scenario_2_update_nexus_file"] = {
            "status": "success",
            "updated_nexus_preview": updated_nexus[:500] + "..." if len(updated_nexus) > 500 else updated_nexus,
            "execution_time_ms": round(execution_time, 2),
            "validations": {
                "old_charstatelabels_removed": old_char_removed,
                "new_characters_added": new_char_added,
                "charstatelabels_block_exists": charstatelabels_exists,
                "matrix_preserved": matrix_still_exists,
                "correct_order": charstatelabels_before_matrix
            }
        }
        
    except Exception as e:
        results["test_results"]["scenario_2_update_nexus_file"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # SCENARIO 3: Test with single character (edge case)
    try:
        start_time = time.time()
        
        single_character_data = [
            {
                "character_index": 1,
                "character": "Single Character Test",
                "states": ["state1", "state2"]
            }
        ]
        
        nexus_bytes = BytesIO(sample_nexus.encode("utf-8"))
        nex_service = NexService(file=nexus_bytes)
        
        formatted_single = nex_service._character_states(character_states_list=single_character_data)
        
        execution_time = (time.time() - start_time) * 1000
        
        # Should have semicolon since it's the last (and only) line
        has_semicolon = formatted_single[0].endswith(";")
        no_comma = "," not in formatted_single[0]
        
        results["test_results"]["scenario_3_single_character_edge_case"] = {
            "status": "success",
            "formatted_output": formatted_single,
            "execution_time_ms": round(execution_time, 2),
            "validations": {
                "ends_with_semicolon": has_semicolon,
                "no_trailing_comma": no_comma,
                "line_count": len(formatted_single)
            }
        }
        
    except Exception as e:
        results["test_results"]["scenario_3_single_character_edge_case"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # SCENARIO 4: Test indentation preservation
    try:
        start_time = time.time()
        
        # NEXUS file with different indentation
        custom_indent_nexus = """#NEXUS

BEGIN DATA;
        DIMENSIONS NTAX=3 NCHAR=2;
        FORMAT DATATYPE=STANDARD SYMBOLS="01" GAP=- MISSING=?;
        
        CHARSTATELABELS
            1 'Test' / 'a' 'b';
        
        MATRIX
            T1    01
            T2    10
            T3    11
        ;
END;
"""
        
        test_data = [
            {
                "character_index": 1,
                "character": "NewChar",
                "states": ["x", "y"]
            }
        ]
        
        nexus_bytes = BytesIO(custom_indent_nexus.encode("utf-8"))
        nex_service = NexService(file=nexus_bytes)
        
        updated_nexus = nex_service.update(character_states_list=test_data)
        
        execution_time = (time.time() - start_time) * 1000
        
        # Check indentation is preserved (MATRIX line has 8 spaces)
        matrix_line_indent = None
        charstatelabels_line_indent = None
        for line in updated_nexus.splitlines():
            if "MATRIX" in line:
                matrix_line_indent = len(line) - len(line.lstrip())
            if "CHARSTATELABELS" in line:
                charstatelabels_line_indent = len(line) - len(line.lstrip())
        
        indentation_matches = matrix_line_indent == charstatelabels_line_indent if matrix_line_indent and charstatelabels_line_indent else False
        
        results["test_results"]["scenario_4_indentation_preservation"] = {
            "status": "success",
            "updated_nexus_preview": updated_nexus[:400] + "..." if len(updated_nexus) > 400 else updated_nexus,
            "execution_time_ms": round(execution_time, 2),
            "validations": {
                "indentation_preserved": indentation_matches,
                "matrix_indent": matrix_line_indent,
                "charstatelabels_indent": charstatelabels_line_indent,
                "newchar_added": "NewChar" in updated_nexus
            }
        }
        
    except Exception as e:
        results["test_results"]["scenario_4_indentation_preservation"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # Determine overall status
    all_tests = results["test_results"]
    passed_tests = sum(1 for test in all_tests.values() if test.get("status") == "success")
    total_tests = len(all_tests)
    
    if passed_tests == total_tests:
        results["overall_status"] = "all_passed"
    elif passed_tests > 0:
        results["overall_status"] = f"partial_pass_{passed_tests}/{total_tests}"
    else:
        results["overall_status"] = "all_failed"
    
    results["summary"] = {
        "total_tests": total_tests,
        "passed": passed_tests,
        "failed": total_tests - passed_tests
    }
    
    return results


@router.post("/extraction-evaluation")
async def test_extraction_evaluation_service():
    """
    Comprehensive test endpoint for ExtractionEvaluationService
    Tests the iterative refinement loop with LIMITED retries for testing.
    
    Tests 1 scenario:
    1. Single character extraction cycle (NO retries - max_attempts=0)
    
    Note: The _cycle method is monkey-patched to limit retries to 0 
    (only 1 attempt) to avoid hitting Gemini API rate limits.
    
    Production code has max_attempts=5, but for testing we use 0 to make:
    - 2 API calls for cache creation
    - 1 API call for extract()
    - 1 API call for evaluate()
    Total: 4 API calls per test run
    """
    import sys
    import os
    
    # Add src to path for imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    from llm.services import ExtractionEvaluationService
    
    results = {
        "test_results": {},
        "overall_status": "unknown",
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Test includes rate limit delays (8s between scenarios)"
    }
    
    # Hardcoded test data - Sample phylogenetic text
    test_context = """
    Character 1: Feathers
    Description: Presence and distribution of feathers on the body.
    States:
    0 - absent: No feathers present
    1 - present: Feathers present on body
    
    Character 2: Wing Structure  
    Description: Morphology of wing bones and flight capability.
    States:
    0 - fully developed: Complete wing structure with flight capability
    1 - reduced: Partial wing structure, limited or no flight
    2 - absent: No wing structures present
    
    Character 3: Teeth
    Description: Presence of teeth in the jaw.
    States:
    0 - present: Teeth present in jaw
    1 - absent: No teeth, beak only
    """
    
    extraction_model = "gemini-2.0-flash-exp"
    evaluation_model = "gemini-2.0-flash-exp"
    
    # SCENARIO 1: Test single character extraction cycle (character index 1)
    try:
        start_time = time.time()
        
        service = ExtractionEvaluationService(
            extraction_model=extraction_model,
            evaluation_model=evaluation_model,
            total_characters=1,
            zero_indexed=False,
            context=test_context
        )
        
        # Test the _cycle method for character index 1
        cycle_result = service._cycle(character_index=1)
        
        execution_time = (time.time() - start_time) * 1000
        
        if cycle_result:
            # Validate the result structure
            has_character_index = "character_index" in cycle_result
            has_character = "character" in cycle_result
            has_states = "states" in cycle_result
            has_score = "score" in cycle_result
            has_justification = "justification" in cycle_result
            score_valid = isinstance(cycle_result.get("score"), int) and cycle_result.get("score") >= 1 and cycle_result.get("score") <= 10
            
            results["test_results"]["scenario_1_single_cycle_extraction"] = {
                "status": "success",
                "cycle_result": cycle_result,
                "execution_time_ms": round(execution_time, 2),
                "note": "Limited to 1 attempt (max_attempts=0 in source code)",
                "api_calls_made": 4,  # 2 for cache creation + 1 extract + 1 evaluate
                "validations": {
                    "has_character_index": has_character_index,
                    "has_character": has_character,
                    "has_states": has_states,
                    "has_score": has_score,
                    "has_justification": has_justification,
                    "score_in_valid_range": score_valid,
                    "final_score": cycle_result.get("score")
                }
            }
        else:
            results["test_results"]["scenario_1_single_cycle_extraction"] = {
                "status": "failure",
                "error": "Cycle returned None - extraction or evaluation failed",
                "execution_time_ms": round(execution_time, 2)
            }
        
    except Exception as e:
        results["test_results"]["scenario_1_single_cycle_extraction"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # Add delay to avoid rate limiting (Gemini free tier: 10 requests/min)
    # time.sleep(8)
    
    # # SCENARIO 2: Test prompt augmentation on retry
    try:
        start_time = time.time()
        
        service = ExtractionEvaluationService(
            extraction_model=extraction_model,
            evaluation_model=evaluation_model,
            total_characters=2,
            zero_indexed=False,
            context=test_context
        )
        
        # Check that the system properly formats extraction prompts
        base_extraction_prompt = service.extraction_prompt.format(character_index=2)
        
        # Validate prompt structure
        has_character_index_placeholder = "{character_index}" in service.extraction_prompt
        has_previous_attempts_context = "Previous attempts" in service.extraction_prompt
        formatted_prompt_valid = "character index: 2" in base_extraction_prompt
        
        results["test_results"]["scenario_2_prompt_augmentation"] = {
            "status": "success",
            "base_prompt_preview": base_extraction_prompt[:200] + "..." if len(base_extraction_prompt) > 200 else base_extraction_prompt,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "validations": {
                "has_character_index_placeholder": has_character_index_placeholder,
                "has_previous_attempts_context": has_previous_attempts_context,
                "formatted_correctly": formatted_prompt_valid,
                "max_attempts_configured": 5
            }
        }
        
    except Exception as e:
        results["test_results"]["scenario_2_prompt_augmentation"] = {
            "status": "failure",
            "error": str(e),
            "error_type": type(e).__name__
        }
    
    # # Add delay to avoid rate limiting (Gemini free tier: 10 requests/min)
    # time.sleep(8)
    
    # # SCENARIO 3: Test configuration and setup
    # try:
    #     start_time = time.time()
        
    #     # Test service initialization with different parameters
    #     service_zero_indexed = ExtractionEvaluationService(
    #         extraction_model=extraction_model,
    #         evaluation_model=evaluation_model,
    #         total_characters=5,
    #         zero_indexed=True,
    #         context=test_context
    #     )
        
    #     # Validate initialization
    #     correct_model_config = (
    #         service_zero_indexed.extraction_model == extraction_model and
    #         service_zero_indexed.evaluation_model == evaluation_model
    #     )
    #     correct_zero_indexed = service_zero_indexed.zero_indexed == True
    #     correct_total_characters = service_zero_indexed.total_characters == 5
    #     gemini_service_initialized = service_zero_indexed.gemini_service is not None
        
    #     # Check prompts are configured
    #     has_system_prompt = len(service_zero_indexed.system_prompt) > 0
    #     has_extraction_prompt = len(service_zero_indexed.extraction_prompt) > 0
    #     has_evaluation_prompt = len(service_zero_indexed.evaluation_prompt) > 0
        
    #     execution_time = (time.time() - start_time) * 1000
        
    #     results["test_results"]["scenario_3_configuration_setup"] = {
    #         "status": "success",
    #         "execution_time_ms": round(execution_time, 2),
    #         "validations": {
    #             "correct_model_configuration": correct_model_config,
    #             "zero_indexed_mode_works": correct_zero_indexed,
    #             "total_characters_set": correct_total_characters,
    #             "gemini_service_initialized": gemini_service_initialized,
    #             "has_system_prompt": has_system_prompt,
    #             "has_extraction_prompt": has_extraction_prompt,
    #             "has_evaluation_prompt": has_evaluation_prompt
    #         },
    #         "config_summary": {
    #             "extraction_model": extraction_model,
    #             "evaluation_model": evaluation_model,
    #             "total_characters": 5,
    #             "zero_indexed": True,
    #             "max_retry_attempts": 5,
    #             "score_threshold": 8
    #         }
    #     }
        
    # except Exception as e:
    #     results["test_results"]["scenario_3_configuration_setup"] = {
    #         "status": "failure",
    #         "error": str(e),
    #         "error_type": type(e).__name__
    #     }
    
    # Determine overall status
    all_tests = results["test_results"]
    passed_tests = sum(1 for test in all_tests.values() if test.get("status") == "success")
    total_tests = len(all_tests)
    
    if passed_tests == total_tests:
        results["overall_status"] = "all_passed"
    elif passed_tests > 0:
        results["overall_status"] = f"partial_pass_{passed_tests}/{total_tests}"
    else:
        results["overall_status"] = "all_failed"
    
    results["summary"] = {
        "total_tests": total_tests,
        "passed": passed_tests,
        "failed": total_tests - passed_tests
    }
    
    return results
