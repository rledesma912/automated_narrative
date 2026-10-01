FROM python:3.12-slim

WORKDIR /app

# Spec-610 (D24): WeasyPrint arma los PDF del guion y del mapa. Necesita pango
# (texto) y una fuente de respaldo con los signos que no traen las del PDF (‖, ▸).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY config/ ./config/
# Spec-610: fuentes libres (OFL) de los PDF.
COPY assets/ ./assets/

RUN mkdir -p /app/data /app/output_stories

EXPOSE 8010

CMD [".venv/bin/python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8010"]
