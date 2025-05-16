import pytest
import json
import time
import uuid
from src.services.message_broker import MessageBroker

class TestMessageBroker:
    def test_send_and_get_task(self, message_broker, redis_client):
        test_file_path = "/tmp/test_file.pdf"
        test_filename = "test_file.pdf"
        
        task_id, result_queue = message_broker.send_classification_task(
            file_path=test_file_path,
            filename=test_filename
        )
        
        assert task_id is not None
        assert result_queue.startswith(message_broker.result_queue_prefix)
        
        task_status_key = f"{message_broker.task_status_prefix}{task_id}"
        task_data_key = f"{message_broker.task_data_prefix}{task_id}"
        
        status_data = redis_client.get(task_status_key)
        assert status_data is not None
        
        status = json.loads(status_data)
        assert status["status"] == "pending"
        assert status["filename"] == test_filename
        assert status["task_id"] == task_id
        
        task_data = redis_client.get(task_data_key)
        assert task_data is not None
        
        task = json.loads(task_data)
        assert task["file_path"] == test_file_path
        assert task["filename"] == test_filename
        assert task["task_id"] == task_id
        assert task["result_queue"] == result_queue
        
        redis_client.delete(task_status_key)
        redis_client.delete(task_data_key)
    
    def test_get_and_update_task_status(self, message_broker, redis_client):
        test_task_id = str(uuid.uuid4())
        test_filename = "status_test.pdf"
        status_key = f"{message_broker.task_status_prefix}{test_task_id}"
        
        initial_status = {
            "status": "pending",
            "filename": test_filename,
            "task_id": test_task_id
        }
        
        redis_client.setex(
            status_key,
            3600, 
            json.dumps(initial_status)
        )
        
        retrieved_status = message_broker.get_task_status(test_task_id)
        assert retrieved_status is not None
        assert retrieved_status["status"] == "pending"
        assert retrieved_status["filename"] == test_filename
        
        updated = message_broker.update_task_status(
            test_task_id,
            "processing"
        )
        assert updated is True
        
        retrieved_status = message_broker.get_task_status(test_task_id)
        assert retrieved_status["status"] == "processing"
        
        updated = message_broker.update_task_status(
            test_task_id,
            "completed",
            predicted_type="invoice",
            success=True
        )
        assert updated is True
        
        retrieved_status = message_broker.get_task_status(test_task_id)
        assert retrieved_status["status"] == "completed"
        assert retrieved_status["predicted_type"] == "invoice"
        assert retrieved_status["success"] is True
        
        non_existent = message_broker.get_task_status("non-existent-task")
        assert non_existent is None
        
        updated = message_broker.update_task_status("non-existent-task", "completed")
        assert updated is False
        
        redis_client.delete(status_key)
    
    def test_send_and_get_classification_result(self, message_broker, redis_client):
        test_queue = f"test_result_queue_{uuid.uuid4()}"
        test_file_type = "invoice"
        
        message_broker.send_classification_result(
            result_queue=test_queue,
            file_type=test_file_type,
            success=True
        )
        
        result = message_broker.get_classification_result(
            result_queue=test_queue,
            timeout=1
        )
        
        assert result is not None
        assert result["predicted_type"] == test_file_type
        assert result["success"] is True
        
        empty_result = message_broker.get_classification_result(
            result_queue="empty_queue",
            timeout=1
        )
        assert empty_result is None 