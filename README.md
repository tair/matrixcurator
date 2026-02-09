# MatrixCurator

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

An AI-powered tool to automate the extraction of morphological character data from scientific publications and generate standardized, FAIR-compliant NEXUS files for phylogenetic analysis. Developed for the [MorphoBank](https://morphobank.org) repository.

---

## Table of Contents

- [About The Project](#about-the-project)
- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Connecting to mb4-server](#connecting-to-mb4-server)
- [Project Structure](#project-structure)
- [Citation](#citation)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contact](#contact)

## About The Project

The curation of biological and paleontological datasets, particularly morphological matrices, is a labor-intensive and error-prone process. Data is often locked away in published literature (PDFs, DOCX files) in inconsistent formats, hindering reproducibility and compliance with FAIR (Findable, Accessible, Interoperable, and Reusable) data principles.

**MatrixCurator** addresses this challenge by leveraging Large Language Models (LLMs) to automate the entire curation workflow. It transforms unstructured character descriptions from research papers into structured, machine-readable `CHARSTATELABELS` blocks within a NEXUS file.

This project aims to:

- **Accelerate research** by drastically reducing manual data entry time.
- **Improve data quality** by minimizing transcription errors and standardizing formats.
- **Enhance data reusability** by producing complete, FAIR-compliant NEXUS files.

## Architecture Overview

| Component            | Technology      | Port  | Purpose                                    |
| -------------------- | --------------- | ----- | ------------------------------------------ |
| **FastAPI Backend**  | FastAPI/Uvicorn | 8001  | REST API for all operations                |
| **React Frontend**   | Vite + React    | 3000  | Interactive demo UI for character extraction|

The FastAPI backend is the **primary interface** and is what gets deployed in Docker. The React frontend communicates with the FastAPI backend via REST API calls.

In production, the FastAPI container joins a **shared Docker network** (`shared_network`) to communicate with other MorphoBank services, including `mb4-server`.

## Key Features

- **Automated Data Extraction**: Uses Google Gemini (`gemini-2.5-flash`) to intelligently parse and extract character names and their corresponding states from uploaded PDF documents. The PDF is sent directly to Gemini's multimodal API for parsing and extraction.
- **AI-Powered Validation**: Multi-agent system where an Evaluator agent (`gemini-2.5-pro`) scores the extraction accuracy (1-10). The system retries with corrective prompts if quality is below threshold (score < 8).
- **NEXUS File Generation**: Integrates extracted character data into existing NEXUS files, creating or updating the `CHARSTATELABELS` block.
- **CSV/Excel to NEXUS/TNT Conversion**: Auto-detects whether uploaded matrix data is morphological (discrete) or numeric (continuous) and converts to the appropriate format (NEXUS or TNT).
- **Context Caching**: Caches the parsed document via Gemini's API caching mechanism (TTL: 1 hour) so that each character extraction call reuses the cached context instead of re-sending the full document. This reduces token consumption significantly for large documents.
- **Concurrent Processing**: Extracts multiple characters in parallel using `ThreadPoolExecutor` (configurable `max_workers`) for faster throughput.
- **Error Tracking**: Integrated Sentry support for exception monitoring in production.

## How It Works

The MatrixCurator pipeline is a multi-step process designed for accuracy and efficiency:

1. **User Input**: A PDF research article is uploaded along with parameters (total characters, page range, zero-indexed flag).

2. **Document Parsing**: The specified page range is extracted from the PDF, and the raw PDF bytes are sent directly to Google Gemini's multimodal API for processing.

3. **AI Core - Multi-Agent Extraction & Evaluation**:
   - **Context Caching**: The parsed document is cached via Gemini's API caching mechanism (TTL: 1 hour) to avoid re-sending the full document on each character extraction call.
   - **Retriever Agent**: For each character number, this agent reads the cached document and extracts the character's name and its list of states as a structured JSON object (`{character, states}`).
   - **Evaluator Agent**: The extraction result is evaluated against the source text, producing a score (1-10) and justification as JSON (`{score, justification}`).
   - **Self-Correction Loop**: If the score is below threshold (8), the process retries with corrective prompts appending previous failed attempts for context.

4. **NEXUS File Update**: The structured JSON data is converted into `CHARSTATELABELS` format and inserted before the `MATRIX` block in the user's original NEXUS file. Any existing `CHARSTATELABELS` block is replaced.

5. **Output**: The final NEXUS file is returned for download.

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [Git](https://git-scm.com/)
- A Google Gemini API key (see [Configuration](#configuration))

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MorphoBankOrg/matrixcurator.git
   cd matrixcurator
   ```

2. **Create the shared Docker network** (required for mb4-server connectivity):
   ```bash
   docker network create shared_network
   ```

3. **Create environment file:**
   ```bash
   cp development.env.template .env
   ```
   Edit `.env` and add your `GEMINI_API_KEY` (see [Configuration](#configuration)).

4. **Build and start the service:**
   ```bash
   docker-compose up --build -d
   ```

5. **Verify the service is running:**
   ```bash
   curl http://localhost:8001/health
   ```

The API will be available at:
- **API Root**: `http://localhost:8001`
- **Swagger Docs**: `http://localhost:8001/docs`
- **Health Check**: `http://localhost:8001/health`

The Docker Compose setup includes volume mounting for hot-reload during development. Changes to `app.py` or files in `src/` will automatically trigger a reload.

## Configuration

MatrixCurator uses environment variables for configuration. Create a `.env` file from the template:

```bash
cp development.env.template .env
```

Edit `.env` and add your values:

```env
# Required: Google Gemini API key
# Obtain from Google AI Studio (https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Environment identifier
ENVIRONMENT=development
```

### Optional Services

The following are optional and only needed for specific features:

| Variable              | Purpose                                   |
| --------------------- | ----------------------------------------- |
| `SENTRY_DSN`          | Sentry error tracking                     |

### Model Configuration

Available models are configured in `src/config/main.py`:

| Display Name       | API Model ID        | Default Role  |
| ------------------ | ------------------- | ------------- |
| Gemini 2.5 Pro     | `gemini-2.5-pro`    | Evaluation    |
| Gemini 2.5 Flash   | `gemini-2.5-flash`  | Extraction    |
| Gemini 2.0 Flash   | `gemini-2.0-flash`  | -             |

### Using the Pre-built Image

Alternatively, you can use the pre-built image without building locally:

```bash
docker pull ghcr.io/morphobankorg/matrixcurator:latest
docker run -p 8001:8001 -e GEMINI_API_KEY=your_key ghcr.io/morphobankorg/matrixcurator:latest
```

### Building & Pushing a Release

Use the included `build.sh` script:

```bash
./build.sh v2025.7.4
```

This builds the Docker image, tags it with both the specified version and `latest`, and pushes to `ghcr.io/morphobankorg/matrixcurator`.

## API Endpoints

### Core Endpoints

| Method | Path                     | Description                                              |
| ------ | ------------------------ | -------------------------------------------------------- |
| `GET`  | `/`                      | API info and version                                     |
| `GET`  | `/health`                | Health check                                             |
| `GET`  | `/test`                  | Test route with capability listing                       |
| `GET`  | `/llm/health`            | LLM/Gemini connectivity and API key check                |

### Processing Endpoints

| Method | Path                     | Description                                              |
| ------ | ------------------------ | -------------------------------------------------------- |
| `POST` | `/api/process-pdf`       | Full PDF processing pipeline (parse → extract → evaluate)|
| `POST` | `/api/upload-csv`        | CSV/Excel to NEXUS/TNT conversion                        |
| `POST` | `/api/custom-extraction` | Custom character extraction with user-provided context    |
| `POST` | `/api/custom-evaluation` | Evaluate quality of an extraction result                  |

### Key Request/Response Examples

**Process PDF** (`POST /api/process-pdf`):
- Form fields: `pdf_file` (file), `total_characters` (int), `page_range` (str, optional), `zero_indexed` (bool), `extraction_model` (str), `evaluation_model` (str)
- Returns: `character_states[]`, `failed_indexes[]`, processing metadata

**Upload CSV** (`POST /api/upload-csv`):
- Form field: `csv_file` (file, `.csv` or `.xlsx`)
- Returns: converted content (NEXUS or TNT format), detection mode, taxa/character counts

**Custom Extraction** (`POST /api/custom-extraction`):
- JSON body: `{context: str, prompt: str}`
- Returns: `{character: str, states: str[]}`

## Connecting to mb4-server

The MatrixCurator container communicates with `mb4-server` via a shared Docker network. This enables the mb4-server (MorphoBank's main application) to call the curator's API endpoints for AI-powered character extraction and CSV conversion.

### Setup

1. **Create the shared network** (if not already created):
   ```bash
   docker network create shared_network
   ```

2. **Start mb4-curator** (it auto-joins `shared_network` via docker-compose):
   ```bash
   docker-compose up -d
   ```

3. **Connect to mb4-server's network** (if mb4-server uses a separate network):
   ```bash
   docker network connect mb4-service_default mb4-curator-api-dev
   ```

Once connected, mb4-server can reach the curator API at `http://mb4-curator-api-dev:8001` using the Docker container name as hostname.

## Project Structure

```
mb4-curator/
├── app.py                          # FastAPI application (primary entry point)
├── tests/
│   └── test_curator.py             # Unit and end-to-end test suite (pytest)
├── src/
│   ├── utils.py                    # Utility functions (page range parsing, etc.)
│   ├── config/
│   │   └── main.py                 # Pydantic settings (models, defaults, workers)
│   ├── llm/
│   │   ├── services.py             # ExtractionEvaluationService (orchestrates extract/evaluate cycle)
│   │   └── external_service.py     # GeminiService (Gemini API client, caching, extract, evaluate)
│   ├── parser/
│   │   ├── services.py             # ParserService (PDF parsing via Gemini)
│   │   ├── csv_converter_service.py# CSVConverterService (CSV/Excel → NEXUS/TNT)
│   │   └── utils.py                # PDFService (page range splitting), temp file helpers
│   └── nex/
│       └── services.py             # NexService (CHARSTATELABELS generation, NEXUS file update)
├── frontend/
│   ├── package.json                # React app dependencies
│   ├── vite.config.js              # Vite config (port 3000, proxy to FastAPI)
│   └── src/
│       ├── App.jsx                 # Main React component
│       ├── components/
│       │   └── CustomExtraction.jsx# Interactive extraction demo component
│       └── services/
│           └── api.js              # Axios API client for FastAPI backend
├── docker-compose.yml              # Docker Compose for development (shared_network)
├── Dockerfile                      # Production Docker image (Python 3.12, FastAPI on port 8001)
├── build.sh                        # Build, tag, and push Docker image to GHCR
├── development.env.template        # Environment variable template
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project metadata (version 2025.7.4)
├── packages.txt                    # System packages (libreoffice) for Dockerfile
└── LICENSE                         # GNU GPL v3
```

## Citation

If you use MatrixCurator or its underlying methodology in your research, please cite the following paper:

Jariwala, S., Long-Fox, B. L., & Berardini, T. Z. (2025). _Advancing FAIR Data Management through AI-Assisted Curation of Morphological Data Matrices_. (Journal and full citation details to be updated upon publication).

**BibTeX:**

```bibtex
@article{Jariwala2025MatrixCurator,
  title   = {Advancing FAIR Data Management through AI-Assisted Curation of Morphological Data Matrices},
  author  = {Jariwala, Shreya and Long-Fox, Brooke L. and Berardini, Tanya Z.},
  year    = {2025},
  journal = {To Be Determined}
}
```

## Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is distributed under the GNU GPL v3 License. See `LICENSE` for more information.

## Acknowledgments

- This work was supported by Phoenix Bioinformatics and the US National Science Foundation (NSF-DBI-2049965 and NSF-EAR-2148768).
- We thank Dr. Maureen A. O'Leary for her ongoing support.
- We acknowledge the use of Google's Gemini models, which were instrumental in the development of this tool.

## Contact

- Shreya Jariwala - [sjariwala@morphobank.org](mailto:sjariwala@morphobank.org)
- Brooke L. Long-Fox (Corresponding Author) - [blongfox@morphobank.org](mailto:blongfox@morphobank.org)

Project Link: [https://github.com/MorphoBankOrg/matrixcurator](https://github.com/MorphoBankOrg/matrixcurator)
