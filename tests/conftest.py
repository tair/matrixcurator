"""
Shared fixtures for the MatrixCurator test suite.
"""

import os
import sys
import pytest
from io import BytesIO

# ---------------------------------------------------------------------------
# Path setup – ensure 'src' is importable the same way the app does it
# ---------------------------------------------------------------------------
SRC_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "src")
sys.path.insert(0, os.path.abspath(SRC_DIR))

# Also make sure the project root (where app.py lives) is on the path so
# `from app import app` works for the TestClient.
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.abspath(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def client():
    """Provide a FastAPI TestClient for the entire test session.
    
    Requires compatible starlette + httpx versions.
    If you see 'Client.__init__() got an unexpected keyword argument app',
    run:  pip install "httpx<0.28" or upgrade fastapi/starlette.
    """
    from fastapi.testclient import TestClient
    from app import app

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Sample NEXUS content
# ---------------------------------------------------------------------------
SAMPLE_NEXUS = """#NEXUS

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


@pytest.fixture()
def nexus_bytes():
    """BytesIO of a small but valid NEXUS file."""
    return BytesIO(SAMPLE_NEXUS.encode("utf-8"))


@pytest.fixture()
def sample_character_states():
    """Typical character-states list used by NexService."""
    return [
        {
            "character_index": 1,
            "character": "Feathers",
            "states": ["present", "absent"],
        },
        {
            "character_index": 2,
            "character": "Wing's Structure",  # has a single-quote to test escaping
            "states": ["fully developed", "reduced", "absent"],
        },
        {
            "character_index": 3,
            "character": "Teeth",
            "states": ["present", "absent"],
        },
    ]


# ---------------------------------------------------------------------------
# Sample CSV content (morphological / standard mode)
# ---------------------------------------------------------------------------
SAMPLE_CSV_STANDARD = (
    ",Feathers,Wing Structure,Teeth\n"
    ",0:absent;1:present,0:fully developed;1:reduced;2:absent,0:present;1:absent\n"
    "Taxon1,0,1,0\n"
    "Taxon2,1,0,1\n"
    "Taxon3,1,2,0\n"
)


@pytest.fixture()
def csv_standard_bytes():
    """CSV bytes representing a morphological (standard) matrix."""
    return SAMPLE_CSV_STANDARD.encode("utf-8")


# ---------------------------------------------------------------------------
# Sample CSV content (numeric / continuous mode)
# ---------------------------------------------------------------------------
SAMPLE_CSV_NUMERIC = (
    ",Length,Width,Height\n"
    "Taxon1,1.23,4.56,7.89\n"
    "Taxon2,2.34,5.67,8.90\n"
    "Taxon3,3.45,6.78,9.01\n"
)


@pytest.fixture()
def csv_numeric_bytes():
    """CSV bytes representing a numeric (continuous) matrix."""
    return SAMPLE_CSV_NUMERIC.encode("utf-8")


# ---------------------------------------------------------------------------
# Sample phylogenetic context text (used by e2e LLM tests)
# ---------------------------------------------------------------------------
SAMPLE_CONTEXT = """
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


@pytest.fixture()
def sample_context():
    return SAMPLE_CONTEXT


# ---------------------------------------------------------------------------
# Skip-if helpers
# ---------------------------------------------------------------------------
def _has_gemini_key() -> bool:
    from dotenv import load_dotenv
    load_dotenv()
    return bool(os.getenv("GEMINI_API_KEY"))


requires_gemini = pytest.mark.skipif(
    not _has_gemini_key(),
    reason="GEMINI_API_KEY not set – skipping live API test",
)

