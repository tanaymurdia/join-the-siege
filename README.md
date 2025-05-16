# Join The Siege Classification System

A robust, scalable document classification system that can handle poorly named files, scale to new industries, and process large volumes of documents.

## Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for local development only)

### Installing Docker

#### Windows
1. Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. Start Docker Desktop after installation

#### macOS
1. Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. Start Docker Desktop after installation

#### Linux
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

## Installation

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

## Data Generation

Generate synthetic data for training the classification model:

```bash
# Generate 1000 documents
python -m model.run_model generate-data --num-samples 1000
```

This will create synthetic documents of various types (drivers licenses, bank statements, invoices, etc.) in the `files/synthetic` directory.

## Model Training

Train the classifier using the generated synthetic data:

```bash
# Train using existing synthetic data
python -m model.run_model train

# Or generate data and train in one step
python -m model.run_model all --num-samples 1000
```

The trained model will be saved in the `model/saved_models` directory.

## Running the Service

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

## API Endpoints

### Classify a File
```
POST /classify_file
```
Upload a file for classification. Returns a task ID for checking the status.

### Check Classification Status
```
GET /classification/{task_id}
```
Check the status and results of a classification task.

### Check Worker Scaling Status
```
GET /scaling/status
```
View the current worker scaling metrics.

### Adjust Worker Count
```
POST /scaling/workers/{count}
```
Adjust the number of worker instances.

### Health Check
```
GET /health
```
Check the health of all services.

## Testing

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


## Full Workflow Example

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