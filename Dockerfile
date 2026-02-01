FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    supervisor \
    --no-install-recommends \
    && apt-get clean \
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
    python -m django setup_data_sources && \
    supervisord -n -c /etc/supervisord.conf
