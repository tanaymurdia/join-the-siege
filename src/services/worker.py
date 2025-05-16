import sys
import os
import time
import signal
import logging
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
        logger.info("Initializing classification worker")
        self.message_broker = MessageBroker()
        self.classifier_service = ClassifierService()
        self.running = True
        
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        logger.info("Classification worker initialized successfully")
        
    def handle_shutdown(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        
    def process_task(self, task):
        logger.info(f"Processing classification task: {task['task_id']}")
        
        try:
            file_path = task['file_path']
            result_queue = task['result_queue']
            task_id = task['task_id']
            
            logger.info(f"Checking file path: {file_path}")
            
            if not os.path.exists(file_path):
                absolute_path = os.path.join('/app', file_path)
                logger.info(f"File not found, trying absolute path: {absolute_path}")
                
                if os.path.exists(absolute_path):
                    file_path = absolute_path
                else:
                    raise FileNotFoundError(f"File not found at {file_path} or {absolute_path}")
            
            logger.info(f"Using file path: {file_path}")
            file_type = self.classifier_service.classify_file(file_path)
            
            logger.info(f"File classified as: {file_type}")
            
            self.message_broker.send_classification_result(
                result_queue=result_queue,
                file_type=file_type,
                success=True,
                task_id=task_id
            )
            
            logger.info(f"Task {task_id} completed successfully")
            
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
                logger.info(f"Removed temporary file {file_path}")
        except Exception as e:
            logger.error(f"Error removing temporary file {file_path}: {str(e)}")
    
    def run(self):
        logger.info("Classification worker starting up...")
        
        while self.running:
            try:
                task = self.message_broker.get_next_classification_task(timeout=1)
                
                if task:
                    self.process_task(task)
                    
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                self.running = False
                
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                time.sleep(1)
                
        logger.info("Worker shutting down...")

if __name__ == "__main__":
    worker = ClassificationWorker()
    worker.run() 