import redis
import json
import os
import uuid
import logging

logger = logging.getLogger('message_broker')

class MessageBroker:
    def __init__(self):
        redis_host = os.environ.get('REDIS_HOST', 'localhost')
        redis_port = os.environ.get('REDIS_PORT', 6379)
        
        logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
        
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            decode_responses=True
        )
        
        self.task_queue = 'classification_tasks'
        self.result_queue_prefix = 'classification_results_'
    
    def send_classification_task(self, file_path, filename):
        task_id = str(uuid.uuid4())
        result_queue = f"{self.result_queue_prefix}{task_id}"
        
        task_data = {
            'task_id': task_id,
            'file_path': file_path,
            'filename': filename,
            'result_queue': result_queue
        }
        
        logger.info(f"Sending task {task_id} to queue with file path: {file_path}")
        self.redis_client.lpush(self.task_queue, json.dumps(task_data))
        
        return task_id, result_queue
    
    def get_classification_result(self, result_queue, timeout=60):
        logger.info(f"Waiting for result in queue {result_queue} with timeout {timeout}s")
        result = self.redis_client.blpop(result_queue, timeout)
        
        if result is None:
            logger.warning(f"Timeout waiting for result in queue {result_queue}")
            return None
            
        channel, data = result
        result_data = json.loads(data)
        
        logger.info(f"Received result from queue {result_queue}: {result_data}")
        return result_data
    
    def send_classification_result(self, result_queue, file_type, success=True, error=None):
        result_data = {
            'predicted_type': file_type,
            'success': success
        }
        
        if error:
            result_data['error'] = str(error)
            
        logger.info(f"Sending result to queue {result_queue}: {result_data}")
        self.redis_client.rpush(result_queue, json.dumps(result_data))
    
    def get_next_classification_task(self, timeout=0):
        task = self.redis_client.blpop(self.task_queue, timeout)
        
        if task is None:
            return None
            
        channel, data = task
        task_data = json.loads(data)
        
        logger.info(f"Received task from queue: {task_data}")
        return task_data 