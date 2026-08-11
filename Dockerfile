FROM python:3.11-slim

# psycopg2-binary needs libpq at runtime even though it bundles its own
# build; slim images don't include it by default.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# main.py's render_html_viewer() opens a local browser and expects a
# writable ./output — neither makes sense in a container. The image's
# entrypoint runs the headless engagement + DB persistence path instead.
ENV OUTPUT_DIR=/app/output
RUN mkdir -p "$OUTPUT_DIR"

ENTRYPOINT ["python", "-m", "scripts.run_headless"]
