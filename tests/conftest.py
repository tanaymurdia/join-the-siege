import pytest
import os
import sys
from pathlib import Path
import redis
import time
import requests
from fastapi.testclient import TestClient
import shutil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import app
from src.services.message_broker import MessageBroker

API_URL = os.environ.get("API_URL", "http://localhost:5000")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
TEST_TIMEOUT = int(os.environ.get("TEST_TIMEOUT", "120")) 

@pytest.fixture
def api_client():
    return TestClient(app)

@pytest.fixture
def redis_client():
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    retry_count = 5
    retry_delay = 2
    
    for i in range(retry_count):
        try:
            client.ping()
            return client
        except redis.exceptions.ConnectionError:
            if i < retry_count - 1:
                print(f"Redis not available yet, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                pytest.skip("Redis server not available after multiple retries")
    
    return client

@pytest.fixture
def message_broker():
    broker = MessageBroker()
    
    retry_count = 5
    retry_delay = 2
    
    for i in range(retry_count):
        try:
            broker.redis_client.ping()
            return broker
        except redis.exceptions.ConnectionError:
            if i < retry_count - 1:
                print(f"Redis not available yet, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                pytest.skip("Redis server not available after multiple retries")
    
    return broker

@pytest.fixture
def test_files():
    files_dir = Path(__file__).parent.parent / "files"
    
    return {
        "pdf": {
            "invoice": files_dir / "invoice_1.pdf",
            "bank_statement": files_dir / "bank_statement_1.pdf",
        },
        "image": {
            "drivers_license": files_dir / "drivers_license_1.jpg",
        }
    }

@pytest.fixture
def temp_dir():
    temp_path = Path(__file__).parent / "temp"
    os.makedirs(temp_path, exist_ok=True)
    yield temp_path
    
    shutil.rmtree(temp_path)

@pytest.fixture
def live_api():
    retry_count = 10
    retry_delay = 3
    
    for i in range(retry_count):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            if response.status_code == 200:
                redis_status = response.json().get("components", {}).get("redis")
                if redis_status == "up":
                    return API_URL
                else:
                    if i < retry_count - 1:
                        print(f"Redis not available through API yet, retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        pytest.skip("Redis service not available through API after multiple retries")
            else:
                if i < retry_count - 1:
                    print(f"API not healthy yet, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    pytest.skip(f"API server not healthy after multiple retries. Status code: {response.status_code}")
        except (requests.RequestException, ValueError) as e:
            if i < retry_count - 1:
                print(f"API not available yet ({str(e)}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                pytest.skip(f"API server not available after multiple retries: {str(e)}")
    
    pytest.skip("API server not available after multiple retries")

@pytest.fixture
def wait_for_task_completion():
    def _wait(task_id, max_wait=TEST_TIMEOUT, interval=1):
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(f"{API_URL}/classification/{task_id}")
                if response.status_code == 200:
                    status = response.json().get("status")
                    if status in ["completed", "failed"]:
                        return response.json()
            except requests.RequestException:
                pass
            
            time.sleep(interval)
        return None
    
    return _wait 