FROM python:3.11-slim

WORKDIR /app

COPY services/atomizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8002

CMD ["python", "services/atomizer/main.py"]
