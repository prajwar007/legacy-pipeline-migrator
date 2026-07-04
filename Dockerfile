FROM python:3.10-slim

WORKDIR /app

# Install the package in its own layer so dependency installs are cached
# across rebuilds when only src/ changes.
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e . paramiko

COPY config/ ./config/
COPY sql/ ./sql/

ENTRYPOINT ["python", "-m", "pipeline.loader"]
CMD ["--help"]
