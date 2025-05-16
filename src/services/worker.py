import sys
import os
import time
import signal
import logging
import threading
from src.services.message_broker import MessageBroker
from src.services.classifier_service import ClassifierService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('worker')
logging.getLogger('message_broker').setLevel(logging.INFO)
logging.getLogger('classifier_service').setLevel(logging.INFO)

class ClassificationWorker:
    def __init__(self):
        worker_id = os.environ.get('WORKER_ID', '0')
        self.worker_id = worker_id
        self.message_broker = MessageBroker()
        self.classifier_service = ClassifierService()
        self.running = True
        self.health_check_interval = 10
        self.last_processed_time = time.time()
        
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        self.health_thread = threading.Thread(target=self.health_check_loop, daemon=True)
        self.health_thread.start()
        
    def handle_shutdown(self, signum, frame):
        self.running = False
        
    def health_check_loop(self):
        while self.running:
            try:
                self.update_health_check_file()
                time.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
    
    def update_health_check_file(self):
        health_path = "/app/worker_healthcheck.txt"
        idleness = time.time() - self.last_processed_time
        
        with open(health_path, "w") as f:
            f.write(f"worker_id: {self.worker_id}\n")
            f.write(f"timestamp: {time.time()}\n")
            f.write(f"idle_seconds: {idleness}\n")
            f.write(f"status: {'healthy' if idleness < 300 else 'idle'}\n")
        
    def process_task(self, task):
        logger.info(f"Processing task: {task['task_id']}")
        self.last_processed_time = time.time()
        
        try:
            file_path = task['file_path']
            result_queue = task['result_queue']
            task_id = task['task_id']
            
            if not os.path.exists(file_path):
                absolute_path = os.path.join('/app', file_path)
                
                if os.path.exists(absolute_path):
                    file_path = absolute_path
                else:
                    raise FileNotFoundError(f"File not found at {file_path} or {absolute_path}")
            
            file_type = self.classifier_service.classify_file(file_path)
            
            self.message_broker.send_classification_result(
                result_queue=result_queue,
                file_type=file_type,
                success=True,
                task_id=task_id
            )
            
            logger.info(f"Task {task_id} completed")
            
            self.cleanup_temp_file(file_path)
            
        except Exception as e:
            logger.error(f"Error processing task {task['task_id']}: {str(e)}")
            
            self.message_broker.send_classification_result(
                result_queue=task['result_queue'],
                file_type="unknown",
                success=False,
                error=str(e),
                task_id=task['task_id']
            )
            
    def cleanup_temp_file(self, file_path):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error removing file {file_path}: {str(e)}")
    
    def run(self):
        while self.running:
            try:
                task = self.message_broker.get_next_classification_task(timeout=1)
                
                if task:
                    self.process_task(task)
                    
            except KeyboardInterrupt:
                self.running = False
                
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                time.sleep(1)

if __name__ == "__main__":
    worker = ClassificationWorker()
    worker.run() 