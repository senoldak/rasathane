# Contributing to CAPitAL

Thank you for your interest in contributing to **CAPitAL** (*CapitolSeeder*)!

We welcome pull requests for bug fixes, performance improvements, data parser enhancements, and new feature integrations.

---

## Development Setup

### 1. Prerequisites
- Python 3.11, 3.12, or 3.13
- Git
- Tesseract OCR (optional, for running live optical character recognition on scanned PDFs)

### 2. Clone and Install
```bash
git clone https://github.com/your-username/CAPitAL.git
cd CAPitAL

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install the package in editable mode with development dependencies
pip install -e ../ortak -e ".[dev]"
```

### 3. Environment Configuration
Copy the configuration template to initialize your local `.env`:
```bash
cp .env.example .env
```

---

## Verification & Testing

Before submitting a Pull Request, verify that all tests and code validations pass:

### 1. Run the Test Suite
```bash
# Run pytest directly
pytest

# Or run with verbose output and coverage
pytest -v --cov=capitolseeder
```

### 2. Validate Code Compilation
```bash
python -m compileall capitolseeder tests
```

### 3. Test Database Ingestion & CLI
```bash
# Seed congressional dataset
python -m capitolseeder.cli seed

# Start development server
python -m capitolseeder.cli serve --reload
```

---

## Code Style & Standards

- **Strict Type Annotations**: All function signatures, API request/response schemas, and data models must have explicit Python type hints.
- **Pydantic v2 Models**: API models must inherit from `pydantic.BaseModel` and utilize Pydantic v2 validation semantics.
- **Async First**: Database operations and HTTP integrations must utilize asynchronous patterns (`async`/`await`, `AsyncSession`, `httpx.AsyncClient`).
- **Security Awareness**: Never disable SSRF validation or hardcode credentials in source files. External URLs must pass `is_safe_webhook_url()`.

---

## Pull Request Guidelines

1. **Branch Naming**: Use descriptive branch names like `feat/ocr-deskew-enhancement` or `fix/simulation-zero-division`.
2. **Atomic Commits**: Keep commits focused and provide clear, imperative commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
3. **Tests Required**: Any new logic or bug fix must include corresponding tests under `tests/`.
4. **Documentation**: Update [README.md](README.md) or [docs/architecture.md](docs/architecture.md) if adding new configuration parameters or public API routes.
