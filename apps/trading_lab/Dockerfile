# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.4.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock* ./
RUN poetry install --only main --no-root --no-directory

COPY src ./src
RUN poetry install --only main

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin tradinglab \
    && mkdir -p /app/logs /app/artifacts \
    && chown -R tradinglab:tradinglab /app

USER tradinglab

EXPOSE 8085

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8085/health', timeout=3)"

CMD ["uvicorn", "trading_lab.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8085"]
