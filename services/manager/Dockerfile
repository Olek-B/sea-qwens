FROM python:3.11-slim

WORKDIR /app

COPY services/manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8006

CMD ["python", "-m", "services.manager.cli"]
