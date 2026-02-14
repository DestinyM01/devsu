# ============================================
# Stage 1: Build
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install dependencies in a virtual env for clean copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Production
# ============================================
FROM python:3.11-slim AS production

# Security: create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY manage.py .
COPY demo/ ./demo/
COPY api/ ./api/

# Environment configuration
ENV DJANGO_SETTINGS_MODULE=demo.settings \
    DJANGO_SECRET_KEY=change-me-in-production \
    DATABASE_NAME=db.sqlite3 \
    DEBUG=False \
    ALLOWED_HOSTS=* \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Collect static files and run migrations
RUN python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput

# Create writable directory for SQLite (if used)
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Expose port
EXPOSE ${PORT}

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1

# Run with gunicorn (production WSGI server)
CMD ["gunicorn", "demo.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
