FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY backend/requirements.txt /app/requirements.txt
COPY backend/requirements-import.txt /app/requirements-import.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/requirements-import.txt

COPY backend/ /app/backend/
COPY ml/ /app/ml/
COPY frontend/ /app/frontend/
COPY parsers/ /app/parsers/
COPY src/ /app/src/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
