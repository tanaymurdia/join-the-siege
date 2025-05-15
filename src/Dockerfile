FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    build-essential \
    libpoppler-cpp-dev \
    pkg-config \
    python3-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the models to avoid downloading during startup
RUN python -c "from transformers import AutoTokenizer, AutoModel; \
    tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased'); \
    model = AutoModel.from_pretrained('distilbert-base-uncased')"

COPY . .

# Set PYTHONPATH for proper module imports
ENV PYTHONPATH=/app

EXPOSE 5000

CMD ["python", "-m", "src.main"] 