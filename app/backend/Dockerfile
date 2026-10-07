FROM python:3.11-slim

WORKDIR /srv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv:/srv/notebooks \
    MODEL_PATH=/models/modelo_priorizacao_alertas.joblib

COPY app/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY notebooks/hooks /srv/notebooks/hooks
COPY app/backend/priorizacao /srv/priorizacao

EXPOSE 8000

CMD ["uvicorn", "priorizacao.main:app", "--host", "0.0.0.0", "--port", "8000"]
