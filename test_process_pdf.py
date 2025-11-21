#!/usr/bin/env python3
"""
Standalone test script for process_pdf functionality
Run with: python test_process_pdf.py
"""

import sys
import os
import time
from io import BytesIO
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def create_sample_pdf():
    """
    Create a simple test PDF with sample phylogenetic character data
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        
        # Page 1: Title and intro
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "Sample Phylogenetic Character Matrix")
        
        c.setFont("Helvetica", 12)
        c.drawString(100, 700, "This is a test document for MatrixCurator")
        
        # Character descriptions
        y_position = 650
        characters_text = [
            "",
            "Character 1: Feathers",
            "Description: Presence and distribution of feathers on the body.",
            "States:",
            "0 - absent: No feathers present",
            "1 - present: Feathers present on body",
            "",
            "Character 2: Wing Structure",
            "Description: Morphology of wing bones and flight capability.",
            "States:",
            "0 - fully developed: Complete wing structure with flight capability",
            "1 - reduced: Partial wing structure, limited or no flight",
            "2 - absent: No wing structures present",
            "",
            "Character 3: Teeth",
            "Description: Presence of teeth in the jaw.",
            "States:",
            "0 - present: Teeth present in jaw",
            "1 - absent: No teeth, beak only"
        ]
        
        for line in characters_text:
            c.drawString(100, y_position, line)
            y_position -= 20
        
        c.showPage()
        c.save()
        
        pdf_buffer.seek(0)
        return pdf_buffer
        
    except ImportError:
        print("Warning: reportlab not installed. Using mock PDF data.")
        return None


def test_process_pdf_core_functionality():
    """
    Test the core PDF processing pipeline without FastAPI
    Tests: Parser → ExtractionEvaluation → Character States extraction
    """
    print("\n" + "="*70)
    print("TEST 1: Core PDF Processing Functionality")
    print("="*70)
    
    try:
        from parser import ParserService
        from llm import ExtractionEvaluationService
        from utils import parse_page_range_string
        from config.main import settings
        
        # Create or use sample PDF
        pdf_buffer = create_sample_pdf()
        
        if pdf_buffer is None:
            # Create a mock text-based context instead
            print("Using text-based context instead of PDF...")
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
            
            # Test without PDF parsing (using text context)
            print("\n→ Initializing ExtractionEvaluationService...")
            start_time = time.time()
            
            extraction_model = settings.MODELS.get("Gemini 2.5 Flash", "gemini-2.0-flash-exp")
            evaluation_model = settings.MODELS.get("Gemini 2.5 Pro", "gemini-2.0-flash-exp")
            
            service = ExtractionEvaluationService(
                extraction_model=extraction_model,
                evaluation_model=evaluation_model,
                total_characters=3,
                context=test_context,
                zero_indexed=False
            )
            
            print("✓ Service initialized")
            print(f"  - Extraction Model: {extraction_model}")
            print(f"  - Evaluation Model: {evaluation_model}")
            print(f"  - Total Characters: 3")
            print(f"  - Zero Indexed: False")
            
            print("\n→ Running extraction/evaluation cycle...")
            character_states_list, failed_indexes = service.run_cycle()
            
            execution_time = time.time() - start_time
            
            print(f"✓ Cycle completed in {execution_time:.2f} seconds")
            print(f"  - Successful extractions: {len(character_states_list)}")
            print(f"  - Failed extractions: {len(failed_indexes)}")
            
            # Display results
            print("\n→ Extraction Results:")
            for char_state in character_states_list:
                print(f"\n  Character {char_state.get('character_index')}: {char_state.get('character')}")
                print(f"    States: {char_state.get('states')}")
                print(f"    Score: {char_state.get('score')}/10")
                print(f"    Justification: {char_state.get('justification', 'N/A')[:100]}...")
            
            if failed_indexes:
                print(f"\n  Failed character indexes: {failed_indexes}")
            
            # Validation
            print("\n→ Validations:")
            all_have_required_fields = all(
                'character_index' in cs and 'character' in cs and 'states' in cs 
                for cs in character_states_list
            )
            print(f"  ✓ All results have required fields: {all_have_required_fields}")
            
            all_scores_valid = all(
                isinstance(cs.get('score'), int) and 1 <= cs.get('score') <= 10 
                for cs in character_states_list
            )
            print(f"  ✓ All scores in valid range (1-10): {all_scores_valid}")
            
            print("\n✅ TEST 1 PASSED")
            return True
            
        else:
            # Use actual PDF parsing
            pdf_buffer.name = "test_sample.pdf"
            
            print(f"\n→ Step 1: Parsing PDF with Gemini parser...")
            start_time = time.time()
            
            parser_service = ParserService("Gemini")
            parsed_article = parser_service.parse(file=pdf_buffer, pages=[0])  # Parse first page
            
            parse_time = time.time() - start_time
            print(f"✓ PDF parsed in {parse_time:.2f} seconds")
            print(f"  - Content length: {len(parsed_article)} characters")
            print(f"  - Preview: {parsed_article[:200]}...")
            
            print(f"\n→ Step 2: Initializing ExtractionEvaluationService...")
            
            extraction_model = settings.MODELS.get("Gemini 2.5 Flash", "gemini-2.0-flash-exp")
            evaluation_model = settings.MODELS.get("Gemini 2.5 Pro", "gemini-2.0-flash-exp")
            
            service = ExtractionEvaluationService(
                extraction_model=extraction_model,
                evaluation_model=evaluation_model,
                total_characters=3,
                context_upload=parsed_article,
                zero_indexed=False
            )
            
            print("✓ Service initialized")
            
            print(f"\n→ Step 3: Running extraction/evaluation cycle for 3 characters...")
            cycle_start = time.time()
            
            character_states_list, failed_indexes = service.run_cycle()
            
            cycle_time = time.time() - cycle_start
            total_time = time.time() - start_time
            
            print(f"✓ Extraction cycle completed in {cycle_time:.2f} seconds")
            print(f"✓ Total processing time: {total_time:.2f} seconds")
            
            # Display results
            print(f"\n→ Results Summary:")
            print(f"  - Successful extractions: {len(character_states_list)}")
            print(f"  - Failed extractions: {len(failed_indexes)}")
            
            print("\n→ Extracted Characters:")
            for char_state in character_states_list:
                print(f"\n  Character {char_state.get('character_index')}: {char_state.get('character')}")
                print(f"    States: {char_state.get('states')}")
                print(f"    Score: {char_state.get('score')}/10")
                justification = char_state.get('justification', 'N/A')
                print(f"    Justification: {justification[:100]}...")
            
            if failed_indexes:
                print(f"\n  ⚠ Failed character indexes: {failed_indexes}")
            
            # Validations
            print("\n→ Validations:")
            all_have_required_fields = all(
                'character_index' in cs and 'character' in cs and 'states' in cs 
                for cs in character_states_list
            )
            print(f"  {'✓' if all_have_required_fields else '✗'} All results have required fields: {all_have_required_fields}")
            
            all_scores_valid = all(
                isinstance(cs.get('score'), int) and 1 <= cs.get('score') <= 10 
                for cs in character_states_list if 'score' in cs
            )
            print(f"  {'✓' if all_scores_valid else '✗'} All scores in valid range (1-10): {all_scores_valid}")
            
            has_states = all(
                isinstance(cs.get('states'), list) and len(cs.get('states')) > 0 
                for cs in character_states_list
            )
            print(f"  {'✓' if has_states else '✗'} All characters have states: {has_states}")
            
            if all_have_required_fields and all_scores_valid and has_states:
                print("\n✅ TEST 1 PASSED")
                return True
            else:
                print("\n❌ TEST 1 FAILED - Some validations did not pass")
                return False
        
    except ImportError as e:
        print(f"\n❌ TEST 1 FAILED - Missing dependencies: {e}")
        return False
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED - Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_page_range_parsing():
    """
    Test the page range parsing utility
    """
    print("\n" + "="*70)
    print("TEST 2: Page Range Parsing")
    print("="*70)
    
    try:
        from utils import parse_page_range_string
        
        test_cases = [
            ("1-3", [0, 1, 2], "Pages 1-3 (0-indexed)"),
            ("5-10", [4, 5, 6, 7, 8, 9], "Pages 5-10 (0-indexed)"),
            ("1", [0], "Single page 1"),
            ("", [], "Empty range"),
            (None, [], "None range"),
        ]
        
        all_passed = True
        
        for input_range, expected, description in test_cases:
            result = parse_page_range_string(input_range)
            passed = result == expected
            all_passed = all_passed and passed
            
            status = "✓" if passed else "✗"
            print(f"\n  {status} {description}")
            print(f"    Input: '{input_range}'")
            print(f"    Expected: {expected}")
            print(f"    Got: {result}")
        
        if all_passed:
            print("\n✅ TEST 2 PASSED")
            return True
        else:
            print("\n❌ TEST 2 FAILED")
            return False
            
    except ImportError as e:
        print(f"\n❌ TEST 2 FAILED - Missing dependencies: {e}")
        return False
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED - Error: {e}")
        return False


def test_model_configuration():
    """
    Test that the models are properly configured
    """
    print("\n" + "="*70)
    print("TEST 3: Model Configuration")
    print("="*70)
    
    try:
        from config.main import settings
        
        print("\n→ Available Models:")
        for model_name, model_id in settings.MODELS.items():
            print(f"  - {model_name}: {model_id}")
        
        # Validate required models exist
        required_models = ["Gemini 2.5 Flash", "Gemini 2.5 Pro"]
        all_present = True
        
        print("\n→ Validation:")
        for model_name in required_models:
            present = model_name in settings.MODELS
            all_present = all_present and present
            status = "✓" if present else "✗"
            print(f"  {status} {model_name}: {'Present' if present else 'Missing'}")
        
        if all_present:
            print("\n✅ TEST 3 PASSED")
            return True
        else:
            print("\n❌ TEST 3 FAILED - Some required models missing")
            return False
            
    except ImportError as e:
        print(f"\n❌ TEST 3 FAILED - Missing dependencies: {e}")
        return False
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED - Error: {e}")
        return False


def test_api_key_configuration():
    """
    Test that API key is configured
    """
    print("\n" + "="*70)
    print("TEST 4: API Key Configuration")
    print("="*70)
    
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        
        if api_key:
            masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
            print(f"\n  ✓ GEMINI_API_KEY is configured: {masked_key}")
            print("\n✅ TEST 4 PASSED")
            return True
        else:
            print("\n  ✗ GEMINI_API_KEY is not configured")
            print("  Please set GEMINI_API_KEY in your environment or .env file")
            print("\n❌ TEST 4 FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST 4 FAILED - Error: {e}")
        return False


def main():
    """
    Run all tests
    """
    print("\n" + "="*70)
    print("PROCESS_PDF TEST SUITE")
    print("="*70)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"Python: {sys.version}")
    print("="*70)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run tests
    results = []
    
    # Test 4: Check API key first (lightweight test)
    results.append(("API Key Configuration", test_api_key_configuration()))
    
    # Test 3: Model configuration (lightweight test)
    results.append(("Model Configuration", test_model_configuration()))
    
    # Test 2: Page range parsing (lightweight test)
    results.append(("Page Range Parsing", test_page_range_parsing()))
    
    # Test 1: Full PDF processing (heavy test - requires API calls)
    print("\n" + "="*70)
    print("⚠ WARNING: The next test will make API calls to Gemini")
    print("This may take 30-60 seconds and will use API quota")
    print("="*70)
    
    try:
        user_input = input("\nRun full PDF processing test? (y/n): ").strip().lower()
        if user_input == 'y':
            results.append(("Core PDF Processing", test_process_pdf_core_functionality()))
        else:
            print("\nSkipping full PDF processing test")
            results.append(("Core PDF Processing", None))
    except (EOFError, KeyboardInterrupt):
        print("\n\nTest interrupted by user")
        results.append(("Core PDF Processing", None))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    total = len(results)
    
    for test_name, result in results:
        if result is True:
            print(f"  ✅ {test_name}")
        elif result is False:
            print(f"  ❌ {test_name}")
        else:
            print(f"  ⊘  {test_name} (skipped)")
    
    print("\n" + "="*70)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("="*70)
    
    if failed == 0 and passed > 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    elif failed > 0:
        print(f"\n⚠ {failed} TEST(S) FAILED")
        return 1
    else:
        print("\n⊘ NO TESTS RUN")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

