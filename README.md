# Heron Classification System

A robust, scalable document classification system that can handle poorly named files, scale to new industries, and process large volumes of documents.

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage Guide](#usage-guide)
  - [Data Generation](#data-generation)
  - [Model Training](#model-training)
  - [Running the Service](#running-the-service)
  - [API Endpoints](#api-endpoints)
  - [Testing](#testing)
- [Complete Workflow](#complete-workflow)
- [Technical Details](#technical-details)
  - [How We Address Key Challenges](#how-we-address-key-challenges)
  - [High-Volume Processing](#high-volume-processing)
  - [Processing Capacity](#processing-capacity)
  - [Future Roadmap](#future-roadmap)

## Overview

The Heron Classification System is designed to automatically classify documents based on their content, regardless of filename quality. It processes documents at scale using a distributed architecture with auto-scaling workers, making it suitable for high-volume environments.

## Key Features

- **Content-based classification** using OCR and BERT embeddings
- **Multiple file format support** (PDF, DOCX, images, CSV)
- **Distributed processing architecture** with Redis queue
- **Auto-scaling worker system** for handling varying loads
- **Comprehensive testing suite** including unit, integration, and load tests
- **Docker-based deployment** for consistent environments

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for local development only)

#### Installing Docker

**Windows**
1. Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. Start Docker Desktop after installation

**macOS**
1. Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. Start Docker Desktop after installation

**Linux**
```bash
# Update package index
sudo apt-get update

# Install Docker dependencies
sudo apt-get install apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up stable repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/tanaymurdia/join-the-siege
   cd join-the-siege
   ```

2. Build the Docker images:
   ```bash
   python -m src.run_service build
   python -m tests.run_tests build
   ```

## Usage Guide

### Data Generation

Generate synthetic data for training the classification model:

```bash
# Generate 1000 documents
python -m model.run_model generate-data --num-samples 1000
```

This will create synthetic documents of various types (drivers licenses, bank statements, invoices, etc.) in the `files/synthetic` directory.

### Model Training

Train the classifier using the generated synthetic data:

```bash
# Train using existing synthetic data
python -m model.run_model train

# Or generate data and train in one step
python -m model.run_model all --num-samples 1000
```

The trained model will be saved in the `model/saved_models` directory.

### Running the Service

Start the classification service:

```bash
# Start all services (API, workers, Redis)
python -m src.run_service start

# Check service status
python -m src.run_service status

# Scale the number of worker instances
python -m src.run_service scale 5

# View service logs
python -m src.run_service logs

# Stop all services
python -m src.run_service stop
```

By default, the API service will be accessible at `http://localhost:5000`.

### API Endpoints

#### Classify a File
```
POST /classify_file
```
Upload a file for classification. Returns a task ID for checking the status.

#### Check Classification Status
```
GET /classification/{task_id}
```
Check the status and results of a classification task.

#### Check Worker Scaling Status
```
GET /scaling/status
```
View the current worker scaling metrics.

#### Adjust Worker Count
```
POST /scaling/workers/{count}
```
Adjust the number of worker instances.

#### Health Check
```
GET /health
```
Check the health of all services.

### Testing

The project includes comprehensive testing tools:

```bash
# Build test images
python -m tests.run_tests build

# Run unit tests
python -m tests.run_tests unit

# Run API tests only
python -m tests.run_tests unit --api-only

# Run service tests only
python -m tests.run_tests unit --services-only

# Run integration tests only
python -m tests.run_tests unit --integration-only
```

## Complete Workflow

Here's a complete example of the workflow from setup to testing:

```bash
# 1. Build Docker images
python -m src.run_service build
python -m tests.run_tests build

# 2. Generate synthetic data and train model
python -m model.run_model all --num-samples 2000 --poorly-named-ratio 0.3

# 3. Start services
python -m src.run_service start

# 4. Scale to desired worker count
python -m src.run_service scale 3

# 5. Test classification with your files
curl -X POST -F 'file=@path_to_your_file.pdf' http://localhost:5000/classify_file

# 6. Run tests
python -m tests.run_tests unit

# 7. Stop services when done
python -m src.run_service stop
```

## Technical Details

### How We Address Key Challenges

#### 1. Handling Poorly Named Files

The original classifier had limitations with poorly named files. Our solution addresses this by:

- **Content-based Classification**: Using OCR and text extraction to analyze the file content rather than relying solely on filenames
- **BERT Embeddings**: Leveraging pre-trained language models to understand document semantics regardless of filename
- **Multi-format Support**: Handling various document formats (PDF, DOCX, images) with specialized extraction techniques
- **Synthetic Data**: Training with a mixture of properly and poorly named files to ensure robust classification

#### 2. Scaling to New Industries

Our implementation enables scaling to new industries through:

- **Diverse Training Data**: Synthetic data generator creates documents from multiple industries (financial, medical, insurance, etc.)
- **Flexible Classification Model**: The model architecture can learn new document types as they are added to the training set
- **Extensible Document Types**: Easy to add new document type definitions in the data generator

#### 3. Processing Larger Volumes

To handle high document volumes efficiently:

- **Distributed Architecture**: Redis-based task queue with multiple worker processes
- **Auto-scaling**: Dynamic worker scaling based on queue length and processing metrics
- **Asynchronous Processing**: Non-blocking API design with task IDs and status checks
- **Resource Management**: Container-level resource allocation and optimization

#### 4. Production Readiness

The system is production-ready with:

- **Containerization**: Docker-based deployment for consistent environments
- **Health Monitoring**: Comprehensive health checks and logging
- **Error Handling**: Robust error handling and recovery mechanisms
- **Scalability**: Horizontal scaling through Docker Compose
- **Testing**: Extensive test suite including unit, integration, and load tests

### High-Volume Processing

The system is designed to handle high volumes of documents through a combination of architectural features and optimizations:

#### Scaling Configuration

To achieve maximum throughput:

```bash
# Scale to 15-20 worker instances for high throughput
python -m src.run_service scale 20

# Set environment variables for optimal performance
export WORKER_REPLICAS=20
```

#### Architecture for High Throughput

- **Distributed Queue**: Redis-based message broker distributes processing across multiple workers
- **Parallel Processing**: Each worker processes documents independently, maximizing throughput
- **Dynamic Worker Scaling**: Worker count can be adjusted based on queue length via the API
- **Efficient Resource Allocation**: Worker containers are configured with resource limits in docker-compose.yml

#### Performance Optimizations

- **Specialized Content Extractors**: Format-specific text extraction for PDF, DOCX, images, and CSV files
- **OCR Pipeline**: Multi-pass OCR with image preprocessing for difficult documents
- **Intelligent Classification**: Hybrid approach combining keyword matching with ML model predictions
- **Temporary File Management**: Automatic cleanup of processed files to prevent disk space issues
- **Model Serialization**: Pre-trained models saved to disk to avoid retraining

These optimizations, combined with the distributed architecture, allow the system to efficiently process large volumes of documents. Additional performance gains can be achieved by upgrading hardware resources and further scaling worker instances.

### Processing Capacity

**Can the system handle 100,000 documents per day?**

Based on the current implementation, the system can theoretically process 100,000 documents per day under certain conditions:

- **Current Throughput**: In our testing, a single worker can process approximately 1-2 documents per minute, depending on document complexity and format
- **Limiting Factors**:
  - OCR processing is particularly time-intensive (5-15 seconds per page for image-based documents)
  - BERT embedding generation adds 1-2 seconds of processing time per document
  - The serialized processing within each worker (one document at a time)

**Realistic Capacity Assessment**:
- With 20 workers running in parallel on decent hardware (8+ cores, 32GB+ RAM):
  - Simple text documents: ~25,000-30,000 documents/day
  - Mixed document types: ~15,000-20,000 documents/day
  - Image-heavy or complex PDFs: ~8,000-12,000 documents/day

To reach the 100,000 documents/day target:
1. Implement the batch processing feature in the future roadmap
2. Increase worker count to 50+ across multiple servers
3. Optimize the content extraction pipeline, particularly OCR processing
4. Implement caching mechanisms for model components
5. Use GPU acceleration for the BERT embedding generation

With these improvements, the system architecture is designed to scale to the 100,000 documents/day target, but the current implementation would require significant hardware resources to achieve this throughput.

### Future Roadmap

While the current implementation addresses the core requirements, we plan to further enhance the system with:

1. **Feedback-Based Learning**: Feedback loop with incorrect classified files to make the model more accurate
2. **CI/CD Pipeline and Analytics**: Set up automated testing and deployment workflows using GitHub Actions or similar tools and Dashboard for monitoring classification performance and accuracy metrics
3. **API Authentication and Protection**: Add OAuth or API key-based authentication for secure access
4. **Document Segmentation**: Advanced techniques to identify and classify different sections within a single document
5. **Batch Processing**: Implement true batch processing capabilities for similar document types
6. **Advanced Caching**: Add Redis-based model and feature caching for faster inference
7. **Memory-Optimized Processing**: Implement streaming processing for very large documents
8. **GPU Acceleration**: Add support for GPU-accelerated inference to significantly increase throughput

These enhancements will further improve the system's capabilities while maintaining its core strengths in handling poorly named files, scaling to new industries, and processing large volumes of documents.