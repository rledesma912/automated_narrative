FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY config/ ./config/
COPY templates/ ./templates/
COPY output_stories/ ./output_stories/
COPY .env ./

RUN mkdir -p /app/output_stories

EXPOSE 8000

CMD [".venv/bin/python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
