# RootCause API

FastAPI backend for RootCause. See the [root README](../../README.md) for setup and
[docs/api-contract.md](../../docs/api-contract.md) for the API contract.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
pytest && ruff check . && ruff format --check . && mypy app
```
