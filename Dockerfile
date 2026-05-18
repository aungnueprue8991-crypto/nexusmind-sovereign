FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget curl git gcc g++ \
    libglib2.0-0 libnss3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
RUN python -m spacy download en_core_web_sm

RUN mkdir -p ./data/chroma ./data/sqlite \
             ./data/skills ./data/memory \
             ./data/dreams ./data/curiosity \
             ./data/improvements ./plugins \
             ./workspace /app/generated_code

COPY --chown=user . .

RUN test -f ./workspace/SOUL.md || echo "# NexusMind\n\nAutonomous AI agent." > ./workspace/SOUL.md
RUN test -f ./workspace/MEMORY.md || echo "# Memory\n\n" > ./workspace/MEMORY.md
RUN test -f ./workspace/AGENTS.md || echo "# Agents\n\n" > ./workspace/AGENTS.md
RUN test -f ./workspace/HEARTBEAT.md || echo "# Heartbeat\n\n" > ./workspace/HEARTBEAT.md

EXPOSE 7860
CMD ["python", "main.py"]
