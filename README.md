# Setup your environment
```
python -m venv .env
source .env/bin/activate
python install poetry
poetry install
```

# In Development
```
poetry run ruff check --fix
poetry run basedpyright
poetry run ruff format
```

# Build Release
```
docker build --target=runtime . -t matrix-bot-admin
```

# Execute Release
```
docker run --name bot-admin -v <path_to_config.toml>:/config.toml matrix-bot-admin
```
