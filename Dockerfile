FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy code
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN pip install -e . uvicorn[standard]

COPY docker/supervisord.conf /etc/

ENV DJANGO_SETTINGS_MODULE=evmap_backend.settings

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD python -m django migrate && \
    python -m django collectstatic --noinput && \
    supervisord -n -c /etc/supervisord.conf
