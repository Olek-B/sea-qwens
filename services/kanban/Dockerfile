FROM python:3.11-slim

WORKDIR /app

COPY services/kanban/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["python", "services/kanban/main.py"]
