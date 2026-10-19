FROM python:3.11-slim
RUN useradd -m -u 1000 app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
USER app
ENV PORT=7860 KRATOS_BIND=0.0.0.0 PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["python", "server.py"]
