FROM python:3.11-slim
WORKDIR /app
RUN pip install kafka-python requests
COPY . .
CMD ["python", "worker.py"]