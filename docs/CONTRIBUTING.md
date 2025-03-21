# Setup your environment
```
uv venv .venv
source .venv/bin/activate
uv sync --frozen
```

# In Development
```
poetry run ruff format
poetry run ruff check
poetry run basedpyright
```
