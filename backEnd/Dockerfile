# Builds with either Docker or Podman.
FROM python:3.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=10 \
    PIP_RETRIES=15 \
    POETRY_REQUESTS_TIMEOUT=10 \
    POETRY_REQUESTS_MAX_RETRIES=15 \
    POETRY_VIRTUALENVS_CREATE=false
WORKDIR /srv/backend

# Dependencies go in a venv so Poetry itself never reaches the runtime image.
FROM base AS deps
# Download caches survive a failed build but are not part of any image layer.
RUN --mount=type=cache,target=/root/.cache pip install poetry==2.5.1 && python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache poetry install --only main --no-root

FROM deps AS test-deps
RUN --mount=type=cache,target=/root/.cache poetry install --no-root

FROM base AS app
ENV PATH=/opt/venv/bin:$PATH
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
ARG APP_VERSION=0.0.0-dev
ENV APP_VERSION=${APP_VERSION}

# docker build --target test: same OS, Python and code as the release, plus pytest.
FROM app AS test
COPY --from=test-deps /opt/venv /opt/venv
COPY pyproject.toml ./
COPY tests ./tests
COPY smoke ./smoke
RUN mkdir /reports && chown -R app:app /reports /srv/backend
USER 10001
CMD ["pytest", "-q", "-p", "no:cacheprovider", "--cov", "--cov-report=term", "--cov-report=xml:/reports/coverage.xml", "--junitxml=/reports/junit.xml"]

FROM app AS runtime
COPY --from=deps /opt/venv /opt/venv
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=4s --start-period=25s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=3)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
