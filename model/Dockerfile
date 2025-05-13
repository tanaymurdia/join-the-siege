FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    build-essential \
    g++ \
    cmake \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN tesseract --version && \
    ls -la /usr/share/tesseract-ocr/ && \
    find /usr -name "tessdata" -type d

ENV OMP_THREAD_LIMIT=1
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

RUN if [ ! -d "$TESSDATA_PREFIX" ]; then \
        TESSDATA_DIR=$(find /usr/share/tesseract-ocr -name "tessdata" -type d | head -n 1); \
        if [ -n "$TESSDATA_DIR" ]; then \
            mkdir -p $(dirname $TESSDATA_PREFIX); \
            ln -s $TESSDATA_DIR $TESSDATA_PREFIX; \
            echo "Created symlink from $TESSDATA_DIR to $TESSDATA_PREFIX"; \
        else \
            echo "Could not find tessdata directory!"; \
        fi \
    fi

ENV TOKENIZERS_PARALLELISM=false

COPY requirements.txt /app/

RUN grep -v "fasttext" requirements.txt > requirements_without_fasttext.txt && \
    pip install --no-cache-dir -r requirements_without_fasttext.txt

RUN pip install --no-cache-dir pybind11>=2.2 && \
    pip install --no-cache-dir fasttext==0.9.2 --no-binary :all: || \
    echo "FastText installation failed, continuing without it"

COPY . /app/

RUN mkdir -p /app/files/synthetic
RUN mkdir -p /app/model/saved_models

ENV PYTHONPATH=${PYTHONPATH}:/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python"] 