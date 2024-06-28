ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-bookworm as builder

ENV POETRY_VERSION=1.8.3

RUN pip install poetry==$POETRY_VERSION

ENV POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app
RUN python -m venv .venv

COPY pyproject.toml poetry.lock ./
COPY matrix_admin_bot ./matrix_admin_bot

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev


FROM python:${PYTHON_VERSION}-slim-bookworm as runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --from=builder /app/matrix_admin_bot /app/matrix_admin_bot


WORKDIR /data
ENTRYPOINT ["matrix-admin-bot"]