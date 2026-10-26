# Contributing to biOF

Thank you for your interest in contributing to **biOF** (Bio-Alpha Terminal)! We welcome contributions from data scientists, quantitative researchers, software engineers, and biotechnology domain experts.

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free experience for everyone. Please be respectful, constructive, and collaborative in all interactions.

---

## Development Setup

### 1. Fork and Clone the Repository

```bash
git clone https://github.com/your-username/biOF.git
cd biOF
```

### 2. Create and Activate a Virtual Environment

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install in Development Mode

```bash
pip install -e ../ortak -e ".[dev]"
```

---

## Contribution Workflow

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. **Follow Coding Standards**:
   - Write clean, type-annotated Python (`typing` and modern Python 3.10+ syntax).
   - Use asynchronous programming patterns (`async`/`await`) for I/O operations and database queries.
   - Follow PEP 8 style conventions.
   - Ensure all user-facing strings, comments, and documentation are written in clear, professional English.
3. **Write and Run Automated Tests**:
   - Add unit or integration tests in `tests/` for any new logic, endpoints, or collector features.
   - Verify that all tests pass locally before opening a pull request:
     ```bash
     pytest -v --cov=bioseeder
     ```
4. **Commit Your Changes**:
   - Use descriptive commit messages following the Conventional Commits specification:
     - `feat: add new regulatory designation boost`
     - `fix: correct clinical trial completion date parser`
     - `docs: update quick start instructions`
5. **Open a Pull Request**:
   - Push your branch to GitHub and submit a Pull Request targeting the `main` branch.
   - Describe what changed and why, linking any relevant issues.

---

## Architecture & Code Guidelines

- **ORM & Database**:
  All database models inherit from `bioseeder.database.Base` and use SQLAlchemy 2.0 `Mapped[...]` attributes. Ensure foreign keys specify cascade behaviors appropriately.
- **Scoring Engine**:
  Quantitative scoring functions in `bioseeder.engine` must remain mathematically bounded between $0.0$ and $100.0$, handling `None` or `NaN` inputs gracefully.
- **Data Collectors**:
  All upstream collectors in `bioseeder.collectors` must inherit from `BaseCollector` to respect rate limits and implement exponential backoff with jitter.
- **Frontend**:
  The Dark Cyber-Biotech Terminal UI uses vanilla ES6, CSS variables (`tokens.css`), and semantic HTML5 without Node.js dependencies. Always escape dynamic user and API values using `escapeHtml()`.

---

## Questions and Support

If you have questions, encounter an issue, or wish to propose an architectural change, please open a GitHub Discussion or submit an Issue.
