FROM python:3.11-slim

WORKDIR /app

# Install system dependencies: git, curl, Node.js, npm
RUN apt-get update && apt-get install -y git curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Clone, build and link custom Qwen Code
RUN git clone https://github.com/Olek-B/qwen-code-my-fixes.git /opt/qwen-code && \
    cd /opt/qwen-code && \
    npm install && \
    npm run build && \
    npm link

COPY services/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PATH="/root/.local/bin:/usr/local/bin:$PATH"

EXPOSE 8004

CMD ["python", "services/worker/main.py"]
