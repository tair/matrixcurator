from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import os
import sys
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import test routes
from test_routes import router as test_router

# Initialize FastAPI app
app = FastAPI(
    title="MatrixCurator API",
    description="API for phylogenetic character data extraction and NEXUS file generation",
    version="2025.7.4"
)

# Include test routes
app.include_router(test_router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request bodies
class CustomExtractionRequest(BaseModel):
    context: str
    prompt: str


class CustomEvaluationRequest(BaseModel):
    context: str
    extraction_result: dict


@app.get("/")
async def root():
    """
    Root endpoint - API information
    """
    return {
        "message": "Welcome to MatrixCurator API",
        "version": "2025.7.4",
        "docs": "/docs",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "MatrixCurator API"
    }


@app.get("/test")
async def test_route():
    """
    Simple test route to verify API is working
    """
    return {
        "message": "Test route successful!",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "data": {
            "modules": ["llm", "nex", "parser"],
            "capabilities": [
                "PDF parsing",
                "DOCX parsing",
                "AI-powered character extraction",
                "NEXUS file generation"
            ]
        }
    }


@app.get("/llm/health")
async def llm_health_check():
    """
    Health check endpoint for LLM/Gemini service
    Tests API key configuration and basic connectivity
    """
    try:
        from google import genai
        from google.genai import types
        
        # Check if API key is configured
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {
                "status": "error",
                "message": "GEMINI_API_KEY not configured",
                "timestamp": datetime.utcnow().isoformat(),
                "configured": False
            }
        
        # Try to initialize the client
        client = genai.Client(api_key=api_key)
        
        # Try a simple test generation
        test_response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents="Say 'OK' if you can read this."
        )
        
        response_text = test_response.text.strip()
        
        return {
            "status": "healthy",
            "message": "LLM service is operational",
            "timestamp": datetime.utcnow().isoformat(),
            "configured": True,
            "api_connected": True,
            "test_response": response_text,
            "model": "gemini-2.0-flash-exp"
        }
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM dependencies not installed: {str(e)}"
        )
    except Exception as e:
        return {
            "status": "error",
            "message": f"LLM service error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
            "configured": api_key is not None if 'api_key' in locals() else False,
            "api_connected": False
        }


@app.post("/api/custom-extraction")
async def custom_extraction(request: CustomExtractionRequest):
    """
    Custom character extraction endpoint for frontend demo
    Accepts user-provided context and extraction prompt
    Returns extracted character and states
    """
    try:
        from llm.external_service import GeminiService
        
        # Validate inputs
        if not request.context.strip():
            raise HTTPException(status_code=400, detail="Context cannot be empty")
        if not request.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
        # System prompt for character extraction
        system_prompt = "You are an expert at extracting phylogenetic character data from scientific texts. Extract the requested character information accurately."
        
        # Initialize GeminiService with user context
        gemini_service = GeminiService(
            extraction_model="gemini-2.0-flash-exp",
            evaluation_model="gemini-2.0-flash-exp",
            system_prompt=system_prompt,
            context=request.context
        )
        
        # Perform extraction
        extraction_result = gemini_service.extract(prompt=request.prompt)
        
        # Return result with metadata
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "extraction": extraction_result,
            "character": extraction_result.get("character"),
            "states": extraction_result.get("states")
        }
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM dependencies not installed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )


@app.post("/api/custom-evaluation")
async def custom_evaluation(request: CustomEvaluationRequest):
    """
    Custom evaluation endpoint for frontend demo
    Evaluates the quality of an extraction result
    Returns score (1-10) and justification
    """
    try:
        from llm.external_service import GeminiService
        
        # Validate inputs
        if not request.context.strip():
            raise HTTPException(status_code=400, detail="Context cannot be empty")
        if not request.extraction_result:
            raise HTTPException(status_code=400, detail="Extraction result cannot be empty")
        
        # System prompt for evaluation
        system_prompt = "You are an expert at evaluating phylogenetic character extraction quality."
        
        # Initialize GeminiService
        gemini_service = GeminiService(
            extraction_model="gemini-2.0-flash-exp",
            evaluation_model="gemini-2.0-flash-exp",
            system_prompt=system_prompt,
            context=request.context
        )
        
        # Create evaluation prompt
        evaluation_prompt = f"""
        Evaluate the quality of this character extraction:
        
        Extracted Character: {request.extraction_result.get('character', 'N/A')}
        Extracted States: {request.extraction_result.get('states', [])}
        
        Rate the extraction from 1-10 based on:
        - Accuracy of character identification
        - Completeness of state information
        - Relevance to the source text
        
        Provide a score (1-10) and justification.
        """
        
        # Perform evaluation
        evaluation_result = gemini_service.evaluate(prompt=evaluation_prompt)
        
        # Return result
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "evaluation": evaluation_result,
            "score": evaluation_result.get("score"),
            "justification": evaluation_result.get("justification")
        }
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM dependencies not installed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


@app.post("/api/process-pdf")
async def process_pdf(
    pdf_file: UploadFile = File(..., description="PDF file to process"),
    total_characters: int = Form(..., description="Total number of morphological characters to extract"),
    page_range: Optional[str] = Form(None, description="Page range (e.g., '3-4' or '5-10')"),
    zero_indexed: bool = Form(False, description="Whether character numbering starts from 0"),
    extraction_model: Optional[str] = Form("Gemini 2.5 Flash", description="Model for character extraction"),
    evaluation_model: Optional[str] = Form("Gemini 2.5 Pro", description="Model for evaluation")
):
    """
    Process a PDF file with Gemini parser and extract character states.
    
    This endpoint:
    1. Accepts a PDF file
    2. Uses Gemini parser to process it
    3. Runs extraction and evaluation for all characters
    4. Returns the extracted character states (without NEXUS file update)
    
    Returns:
        - character_states: List of successfully extracted character data
        - failed_indexes: List of character indices that failed extraction
        - metadata: Processing information (time, counts, etc.)
    """
    try:
        from parser import ParserService
        from llm import ExtractionEvaluationService
        from utils import parse_page_range_string
        from config.main import settings
        import time
        
        # Validate PDF file type
        if not pdf_file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        # Validate models
        if extraction_model not in settings.MODELS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid extraction model. Available models: {list(settings.MODELS.keys())}"
            )
        if evaluation_model not in settings.MODELS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid evaluation model. Available models: {list(settings.MODELS.keys())}"
            )
        
        # Convert model names to API IDs
        extraction_model_id = settings.MODELS[extraction_model]
        evaluation_model_id = settings.MODELS[evaluation_model]
        
        start_time = time.time()
        
        # Step 1: Read PDF file
        pdf_bytes = await pdf_file.read()
        pdf_stream = BytesIO(pdf_bytes)
        pdf_stream.name = pdf_file.filename  # Add name attribute for compatibility
        
        # Step 2: Parse page range (handle empty range)
        pages = parse_page_range_string(page_range)
        
        # If no page range specified, use all pages
        if not pages:
            from PyPDF2 import PdfReader
            pdf_reader = PdfReader(pdf_stream)
            total_pages = len(pdf_reader.pages)
            pages = list(range(0, total_pages))  # 0-indexed for PyPDF2
            pdf_stream.seek(0)  # Reset stream after reading
        
        # Step 3: Parse PDF with Gemini parser
        parser_service = ParserService("Gemini")
        parsed_article = parser_service.parse(file=pdf_stream, pages=pages)
        
        # Step 4: Initialize extraction/evaluation service
        extraction_evaluation_service = ExtractionEvaluationService(
            extraction_model=extraction_model_id,
            evaluation_model=evaluation_model_id,
            total_characters=total_characters,
            context_upload=parsed_article,
            zero_indexed=zero_indexed
        )
        
        # Step 5: Run extraction/evaluation cycle
        character_states_list, failed_indexes = extraction_evaluation_service.run_cycle()
        
        end_time = time.time()
        processing_time = round(end_time - start_time, 2)
        
        # Prepare response
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "filename": pdf_file.filename,
                "total_characters": total_characters,
                "page_range": page_range or "all pages",
                "zero_indexed": zero_indexed,
                "extraction_model": extraction_model,
                "evaluation_model": evaluation_model,
                "processing_time_seconds": processing_time,
                "successful_extractions": len(character_states_list),
                "failed_extractions": len(failed_indexes)
            },
            "character_states": character_states_list,
            "failed_indexes": failed_indexes
        }
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Required dependencies not installed: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        error_str = str(e)
        # Check for quota exhaustion errors
        if "429" in error_str or "exceeded your current quota" in error_str.lower() or "RESOURCE_EXHAUSTED" in error_str or "quota exceeded" in error_str.lower():
            raise HTTPException(
                status_code=429,
                detail=f"API quota exceeded: {error_str}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed: {str(e)}"
            )


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        reload=True  # Enable auto-reload during development
    )
