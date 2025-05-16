import os
import time
import logging
import threading
import subprocess
import redis

logger = logging.getLogger('worker_scaling')

class WorkerScalingService:
    def __init__(self, redis_client=None):
        self.redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_port = int(os.environ.get('REDIS_PORT', 6379))
        
        self.redis_client = redis_client or redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            decode_responses=True
        )
            
        self.worker_min_count = int(os.environ.get('MIN_WORKERS', 2))
        self.worker_max_count = int(os.environ.get('MAX_WORKERS', 10))
        self.current_worker_count = int(os.environ.get('WORKER_REPLICAS', 3))
        
        self.task_queue = 'classification_tasks'
        self.queue_high_threshold = int(os.environ.get('QUEUE_HIGH_THRESHOLD', 20))
        self.queue_low_threshold = int(os.environ.get('QUEUE_LOW_THRESHOLD', 5))
        self.metric_key = 'worker_scaling_metrics'
        self.scaling_interval = 30
        self.running = True
        self.last_scaling_time = time.time() - 120
    
    def start_monitoring(self):
        self.monitoring_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitoring_thread.start()
        
    def stop_monitoring(self):
        self.running = False
        
    def get_queue_length(self):
        try:
            return self.redis_client.llen(self.task_queue)
        except Exception as e:
            logger.error(f"Error getting queue length: {str(e)}")
            return 0
            
    def get_worker_stats(self):
        try:
            metrics = self.redis_client.hgetall(self.metric_key)
            if metrics and "current_worker_count" in metrics:
                return int(float(metrics["current_worker_count"]))
                
            return int(os.environ.get('WORKER_REPLICAS', self.current_worker_count))
        except Exception as e:
            logger.error(f"Error getting worker stats: {str(e)}")
            return self.current_worker_count
    
    def scale_workers(self, target_count):
        target_count = max(self.worker_min_count, min(self.worker_max_count, target_count))
        
        if target_count == self.current_worker_count:
            return
            
        logger.info(f"Scaling workers: {self.current_worker_count} → {target_count}")
        
        try:
            subprocess.run(
                ["docker-compose", "up", "--scale", f"worker={target_count}", "-d"],
                capture_output=True,
                check=False
            )
            
            self.redis_client.hmset(self.metric_key, {
                "last_scaling_time": time.time(),
                "current_worker_count": target_count,
                "target_worker_count": target_count
            })
            
            self.last_scaling_time = time.time()
            self.current_worker_count = target_count
            
        except Exception as e:
            logger.error(f"Error during scaling: {str(e)}")
    
    def monitor_loop(self):
        while self.running:
            try:
                if time.time() - self.last_scaling_time < 60:
                    time.sleep(self.scaling_interval)
                    continue
                    
                queue_length = self.get_queue_length()
                worker_count = self.get_worker_stats()
                
                self.redis_client.hmset(self.metric_key, {
                    "timestamp": time.time(),
                    "queue_length": queue_length,
                    "worker_count": worker_count,
                    "min_workers": self.worker_min_count,
                    "max_workers": self.worker_max_count
                })
                
                if queue_length > self.queue_high_threshold and worker_count < self.worker_max_count:
                    new_count = min(self.worker_max_count, worker_count + max(1, queue_length // 10))
                    self.scale_workers(new_count)
                elif queue_length < self.queue_low_threshold and worker_count > self.worker_min_count:
                    self.scale_workers(worker_count - 1)
                    
            except Exception as e:
                logger.error(f"Error in scaling loop: {str(e)}")
                
            time.sleep(self.scaling_interval) 