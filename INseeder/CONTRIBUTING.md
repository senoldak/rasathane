# Contributing to INseeder

Thank you for your interest in contributing to **INseeder**! We welcome contributions from the community to improve detection models, add broker adapters, enhance UI features, and fix bugs.

---

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please be respectful and constructive in all interactions.

---

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork locally**:
   ```bash
   git clone https://github.com/<your-username>/inseeder.git
   cd inseeder
   ```
3. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Verify existing tests pass**:
   ```bash
   pytest -v
   ```

---

## Development Guidelines

### 1. Code Standards
- Adhere to **PEP 8** standards.
- Use explicit type annotations where practical.
- Keep functions focused and modules decoupled.

### 2. Test-Driven Development (TDD)
- All new features and bug fixes must include corresponding tests under the `tests/` directory.
- Use `pytest` and `pytest-asyncio` for asynchronous tests.
- When adding broker integrations or network collectors, use mocks (`unittest.mock.AsyncMock`) and avoid making live network calls in unit tests.

### 3. SEC Fair Access Compliance
- Any changes to `inseeder/collectors/sec_edgar.py` must maintain compliance with the SEC Fair Access policy (custom User-Agent with contact details, throttled request rates).

---

## Pull Request Checklist

Before submitting your pull request, verify:
- [ ] All tests pass: `pytest -v`
- [ ] Code is formatted and clean.
- [ ] Any new configuration options are documented in `.env.example` and `README.md`.
- [ ] Commit messages are descriptive and concise.
- [ ] The PR description clearly explains the problem and the proposed solution.
