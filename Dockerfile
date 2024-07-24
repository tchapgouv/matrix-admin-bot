ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-bookworm as builder

ENV POETRY_VERSION=1.8.3

RUN pip install poetry==$POETRY_VERSION poetry-dynamic-versioning[plugin]

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./
COPY matrix_admin_bot ./matrix_admin_bot
COPY matrix_command_bot ./matrix_command_bot
# Needed to derivate version from git tag
COPY .git ./.git

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev --compile

RUN rm -rf .git

FROM python:${PYTHON_VERSION}-slim-bookworm as runtime

COPY --from=builder /app /app

WORKDIR /data
ENTRYPOINT ["/app/.venv/bin/matrix-admin-bot"]
