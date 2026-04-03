FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-cache-dir git && rm -rf /var/lib/apt/lists/*

COPY services/tester/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8005

CMD ["python", "services/tester/main.py"]
