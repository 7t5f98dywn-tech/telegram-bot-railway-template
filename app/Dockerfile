# Production image: small, non-root, no build cache baked in.
FROM python:3.12-slim

# Never write .pyc files; flush logs immediately (Railway log streaming).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so source edits don't bust the pip layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged user — the bot never needs root.
RUN useradd --create-home --uid 10001 botuser
COPY --chown=botuser:botuser . .
USER botuser

# Railway injects PORT at runtime; EXPOSE is documentation only.
EXPOSE 8080

CMD ["python", "main.py"]
