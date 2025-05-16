import pytest
import time
import redis
from unittest.mock import MagicMock, patch
from src.services.worker_scaling import WorkerScalingService

@pytest.fixture
def mock_redis_client():
    redis_client = MagicMock()
    redis_client.llen.return_value = 10
    redis_client.hgetall.return_value = {
        "current_worker_count": "3",
        "min_workers": "2",
        "max_workers": "10",
        "worker_count": "3",
        "queue_length": "10",
        "timestamp": str(time.time()),
        "last_scaling_time": str(time.time() - 300)
    }
    redis_client.hmset.return_value = True
    redis_client.hset.return_value = True
    return redis_client

@pytest.fixture
def scaling_service(mock_redis_client):
    service = WorkerScalingService(redis_client=mock_redis_client)
    service.current_worker_count = 3
    return service

def test_init(scaling_service):
    assert scaling_service.worker_min_count == 2
    assert scaling_service.worker_max_count == 10
    assert scaling_service.current_worker_count == 3
    assert scaling_service.queue_high_threshold == 20
    assert scaling_service.queue_low_threshold == 5
    assert scaling_service.task_queue == 'classification_tasks'

def test_get_queue_length(scaling_service, mock_redis_client):
    mock_redis_client.llen.return_value = 15
    assert scaling_service.get_queue_length() == 15
    mock_redis_client.llen.assert_called_once_with(scaling_service.task_queue)

def test_get_queue_length_exception(scaling_service, mock_redis_client):
    mock_redis_client.llen.side_effect = redis.exceptions.RedisError("Test error")
    assert scaling_service.get_queue_length() == 0
def test_get_worker_stats_from_redis(scaling_service, mock_redis_client):
    mock_redis_client.hgetall.return_value = {
        "current_worker_count": "4",
        "worker_count": "4" 
    }
    
    assert scaling_service.get_worker_stats() == 4
    mock_redis_client.hgetall.assert_called_with(scaling_service.metric_key)

@patch('os.environ.get')
def test_get_worker_stats_from_env(mock_env_get, scaling_service, mock_redis_client):
    mock_redis_client.hgetall.return_value = {}  
    mock_env_get.return_value = "5"
    
    assert scaling_service.get_worker_stats() == 5
    mock_env_get.assert_called_with('WORKER_REPLICAS', scaling_service.current_worker_count)

def test_scale_workers_success(scaling_service, mock_redis_client):
    with patch('subprocess.run') as mock_run:
        docker_check_result = MagicMock()
        docker_check_result.returncode = 0
        
        docker_scale_result = MagicMock()
        docker_scale_result.returncode = 0
        
        mock_run.side_effect = [docker_check_result, docker_scale_result]
        
        scaling_service.scale_workers(5)
        assert scaling_service.current_worker_count == 5
        assert mock_run.call_count == 2

def test_scale_workers_same_count(mock_redis_client, scaling_service):
    with patch('subprocess.run') as mock_run:
        scaling_service.scale_workers(3)
        mock_run.assert_not_called()

def test_scale_workers_min_limit(scaling_service, mock_redis_client):
    with patch('subprocess.run') as mock_run:
        docker_check_result = MagicMock()
        docker_check_result.returncode = 0
        
        docker_scale_result = MagicMock()
        docker_scale_result.returncode = 0
        
        mock_run.side_effect = [docker_check_result, docker_scale_result]
        
        scaling_service.scale_workers(1)
        assert scaling_service.current_worker_count == 2
        assert mock_run.call_count == 2
        
        calls = mock_run.call_args_list
        assert "worker=2" in str(calls[1][0][0])

def test_scale_workers_max_limit(scaling_service, mock_redis_client):
    with patch('subprocess.run') as mock_run:
        docker_check_result = MagicMock()
        docker_check_result.returncode = 0
        
        docker_scale_result = MagicMock()
        docker_scale_result.returncode = 0
        
        mock_run.side_effect = [docker_check_result, docker_scale_result]
        
        scaling_service.scale_workers(15)
        assert scaling_service.current_worker_count == 10
        assert mock_run.call_count == 2
        
        calls = mock_run.call_args_list
        assert "worker=10" in str(calls[1][0][0])  

def test_scale_workers_docker_not_available(scaling_service, mock_redis_client):
    with patch('subprocess.run') as mock_run:
        docker_check_result = MagicMock()
        docker_check_result.returncode = 1  
        
        mock_run.return_value = docker_check_result
        
        scaling_service.scale_workers(5)
        assert scaling_service.current_worker_count == 5  
        assert mock_run.call_count == 1  

def test_scale_workers_command_failure(scaling_service, mock_redis_client):
    with patch('subprocess.run') as mock_run:
        docker_check_result = MagicMock()
        docker_check_result.returncode = 0  
        
        docker_scale_result = MagicMock()
        docker_scale_result.returncode = 1 
        docker_scale_result.stderr = "Command failed"
        
        mock_run.side_effect = [docker_check_result, docker_scale_result]
        
        original_worker_count = scaling_service.current_worker_count
        scaling_service.scale_workers(5)
        
        assert scaling_service.current_worker_count == original_worker_count
        assert mock_run.call_count == 2

@patch('src.services.worker_scaling.WorkerScalingService.scale_workers')
def test_check_and_apply_scaling_up(mock_scale, scaling_service):
    queue_length = 25  
    worker_count = 3   
    
    scaling_service.check_and_apply_scaling(queue_length, worker_count)
    
    mock_scale.assert_called_once_with(5)

@patch('src.services.worker_scaling.WorkerScalingService.scale_workers')
def test_check_and_apply_scaling_down(mock_scale, scaling_service):
    queue_length = 3   
    worker_count = 5  
    scaling_service.current_worker_count = 5
    
    scaling_service.check_and_apply_scaling(queue_length, worker_count)
    
    mock_scale.assert_called_once_with(4)

@patch('src.services.worker_scaling.WorkerScalingService.scale_workers')
def test_check_and_apply_scaling_no_change(mock_scale, scaling_service):
    queue_length = 10  
    worker_count = 3
    
    result = scaling_service.check_and_apply_scaling(queue_length, worker_count)
    
    assert result is False
    mock_scale.assert_not_called()

def test_start_stop_monitoring(scaling_service):
    with patch('threading.Thread') as mock_thread:
        instance = mock_thread.return_value
        scaling_service.start_monitoring()
        mock_thread.assert_called_once()
        instance.start.assert_called_once()
        
        assert scaling_service.running is True
        scaling_service.stop_monitoring()
        assert scaling_service.running is False 