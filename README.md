# Setup your environment
```
uv venv .env
source .env/bin/activate
uv sync
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
