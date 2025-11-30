FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy code
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN pip install -e . uvicorn[standard]

ENV DJANGO_SETTINGS_MODULE=evmap_backend.settings

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD python -m django migrate && \
    python -m django collectstatic --noinput && \
    uvicorn evmap_backend.asgi:application --host 0.0.0.0 --port 8000
