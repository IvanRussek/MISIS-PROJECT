FROM python:3.10-slim-buster 

ARG SERVICE_PORT=8501
ENV SERVICE_PORT=${SERVICE_PORT}

COPY . /app
WORKDIR /app

RUN python -m pip install --upgrade pip 
RUN python -m pip install -r requirements.txt

RUN apt update && apt install -y ca-certificates curl

RUN (export DRY_RUN=True; streamlit run MISIS.py &) && sleep 5 && curl http://localhost:${SERVICE_PORT}/

HEALTHCHECK CMD curl --fail http://localhost:${SERVICE_PORT}/_stcore/health
CMD ["streamlit", "run", "MISIS.py", "--server.port=8501", "--server.address=0.0.0.0"]
ENTRYPOINT streamlit run MISIS.py --server.port=${SERVICE_PORT} --server.address=0.0.0.0
