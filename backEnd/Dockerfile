FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /srv/backend
COPY pyproject.toml poetry.lock ./
RUN python -m pip install --upgrade pip poetry==2.5.1 \
    && poetry install --only main --no-root \
    && python -m pip install "uvicorn[standard]" "psycopg[binary]" \
    && addgroup --system app && adduser --system --ingroup app app
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
USER app
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=4s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=3)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
