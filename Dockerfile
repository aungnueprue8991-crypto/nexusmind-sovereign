FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget curl git gcc g++ \
    libglib2.0-0 libnss3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set up user and working directory
RUN useradd -m -u 1000 user
WORKDIR /app

# Copy requirements and install (as root for build efficiency)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
RUN python -m spacy download en_core_web_sm

# Copy application files and set ownership
COPY --chown=user . .

# Set up runtime environment
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Ensure runtime directories exist
RUN mkdir -p ./data/chroma ./data/sqlite ./data/skills ./data/memory ./plugins ./workspace ./generated_code

EXPOSE 7860
CMD ["python", "main.py"]
