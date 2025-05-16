import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

@pytest.fixture
def mock_scaling_service():
    with patch('src.main.scaling_service') as mock:
        mock.get_worker_stats.return_value = 3
        mock.current_worker_count = 3
        mock.worker_min_count = 2
        mock.worker_max_count = 10
        mock.get_queue_length.return_value = 0
        
        mock.redis_client = MagicMock()
        mock.redis_client.hgetall.return_value = {
            "current_worker_count": "3",
            "min_workers": "2",
            "max_workers": "10",
            "worker_count": "3",
            "queue_length": "0",
            "timestamp": "1628097823.456",
            "last_scaling_time": "1628097800.123"
        }
        
        yield mock

def test_get_scaling_status(mock_scaling_service):
    response = client.get("/scaling/status")
    assert response.status_code == 200
    data = response.json()
    
    assert "current_worker_count" in data
    assert data["current_worker_count"] == 3.0
    assert data["min_workers"] == 2.0
    assert data["max_workers"] == 10.0
    assert "queue_length" in data
    assert "timestamp" in data
    assert "last_scaling_time" in data

def test_get_scaling_status_redis_error(mock_scaling_service):
    mock_scaling_service.redis_client.hgetall.side_effect = Exception("Redis error")
    mock_scaling_service.get_worker_stats.return_value = 3
    mock_scaling_service.get_queue_length.return_value = 5
    
    response = client.get("/scaling/status")
    assert response.status_code == 200
    data = response.json()
    
    assert data["current_worker_count"] == 3.0
    assert data["worker_count"] == 3.0
    assert data["queue_length"] == 5.0

def test_set_worker_count(mock_scaling_service):
    response = client.post("/scaling/workers/5")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Worker count set to 5"}
    mock_scaling_service.scale_workers.assert_called_once_with(5)

def test_set_worker_count_error(mock_scaling_service):
    mock_scaling_service.scale_workers.side_effect = Exception("Scaling error")
    response = client.post("/scaling/workers/5")
    assert response.status_code == 500
    assert "error" in response.json()["detail"]

def test_set_worker_count_invalid(mock_scaling_service):
    response = client.post("/scaling/workers/0")
    assert response.status_code == 422
    
    response = client.post("/scaling/workers/21")
    assert response.status_code == 422

def test_health_check_with_workers(mock_scaling_service):
    mock_scaling_service.get_worker_stats.return_value = 3
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["components"]["api"] == "up"
    assert data["components"]["redis"] == "up"
    assert data["components"]["workers"]["status"] == "up"
    assert data["components"]["workers"]["count"] == 3

def test_health_check_no_workers(mock_scaling_service):
    mock_scaling_service.get_worker_stats.return_value = 0
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "degraded"
    assert data["components"]["api"] == "up"
    assert data["components"]["redis"] == "up"
    assert data["components"]["workers"]["status"] == "down"
    assert data["components"]["workers"]["count"] == 0

@patch('src.main.message_broker')
def test_health_check_redis_down(mock_message_broker, mock_scaling_service):
    mock_message_broker.redis_client.ping.side_effect = Exception("Redis error")
    
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    
    assert data["status"] == "unhealthy"
    assert data["components"]["api"] == "up"
    assert data["components"]["redis"] == "down"
    assert data["components"]["workers"]["status"] == "unknown" 