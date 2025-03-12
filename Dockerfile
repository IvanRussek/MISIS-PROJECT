FROM python:3.10-slim-bullseye

ARG SERVICE_PORT=8501
ENV SERVICE_PORT=${SERVICE_PORT}

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    curl \
    ca-certificates \
    wait-for-it \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
WORKDIR /app

RUN python -m pip install --upgrade pip
RUN python -m pip install --use-deprecated=legacy-resolver -r requirements.txt

RUN (streamlit run MISIS.py --server.port=${SERVICE_PORT} --server.address=0.0.0.0 &) && \
    wait-for-it localhost:${SERVICE_PORT} --timeout=30 -- echo "App started successfully"

HEALTHCHECK CMD curl --fail http://localhost:${SERVICE_PORT}/_stcore/health

ENTRYPOINT ["streamlit", "run", "MISIS.py", "--server.port=${SERVICE_PORT}", "--server.address=0.0.0.0"]
