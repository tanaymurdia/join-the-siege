import os
import time
import logging
import threading
import subprocess
import redis
import json

logger = logging.getLogger('worker_scaling')

class WorkerScalingService:
    def __init__(self, redis_client=None):
        self.redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_port = int(os.environ.get('REDIS_PORT', 6379))
        
        if redis_client:
            self.redis_client = redis_client
        else:
            self.redis_client = redis.Redis(
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
        
        logger.info(f"Initialized worker scaling service with min={self.worker_min_count}, max={self.worker_max_count}, current={self.current_worker_count}")
    
    def start_monitoring(self):
        self.monitoring_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Started worker scaling monitoring thread")
        
    def stop_monitoring(self):
        self.running = False
        logger.info("Stopping worker scaling monitoring")
        
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
        except Exception as e:
            logger.debug(f"Could not get worker count from Redis: {str(e)}")
        
        try:
            worker_count = int(os.environ.get('WORKER_REPLICAS', self.current_worker_count))
            return worker_count
        except Exception as e:
            logger.debug(f"Could not get worker count from environment: {str(e)}")
        
        try:
            docker_exists = subprocess.run(
                ["which", "docker"],
                capture_output=True,
                text=True
            ).returncode == 0
            
            if docker_exists:
                result = subprocess.run(
                    ["docker", "ps", "--filter", "name=worker", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    return len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        except Exception as e:
            logger.error(f"Error getting worker stats: {str(e)}")
        
        return self.current_worker_count
    
    def scale_workers(self, target_count):
        if target_count == self.current_worker_count:
            return
            
        if target_count < self.worker_min_count:
            target_count = self.worker_min_count
            
        if target_count > self.worker_max_count:
            target_count = self.worker_max_count
            
        logger.info(f"Scaling workers from {self.current_worker_count} to {target_count}")
        
        docker_available = False
        command_success = False
        
        try:
            docker_exists = subprocess.run(
                ["which", "docker-compose"],
                capture_output=True,
                text=True
            ).returncode == 0
            
            if docker_exists:
                docker_available = True
                result = subprocess.run(
                    ["docker-compose", "up", "--scale", f"worker={target_count}", "-d"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    command_success = True
                else:
                    logger.error(f"Failed to scale workers: {result.stderr}")
                    return
            
            if not docker_available or command_success:
                self.redis_client.hset(
                    self.metric_key,
                    "last_scaling_time",
                    time.time()
                )
                self.redis_client.hset(
                    self.metric_key,
                    "current_worker_count",
                    target_count
                )
                self.redis_client.hset(
                    self.metric_key,
                    "target_worker_count", 
                    target_count
                )
                self.last_scaling_time = time.time()
                
                self.current_worker_count = target_count
                
                if not docker_available:
                    logger.info(f"Docker not available in container, storing scaling intent for external orchestration")
                
                logger.info(f"Updated worker count to {target_count}")
            
        except Exception as e:
            logger.error(f"Error during worker scaling: {str(e)}")
    
    def check_and_apply_scaling(self, queue_length, worker_count):
        if queue_length > self.queue_high_threshold and worker_count < self.worker_max_count:
            target_count = min(
                self.worker_max_count,
                self.current_worker_count + max(1, queue_length // 10)
            )
            self.scale_workers(target_count)
            return True
        elif queue_length < self.queue_low_threshold and worker_count > self.worker_min_count:
            target_count = max(
                self.worker_min_count,
                self.current_worker_count - 1
            )
            self.scale_workers(target_count)
            return True
        return False
    
    def monitor_loop(self):
        logger.info("Starting worker scaling monitoring loop")
                
        while self.running:
            try:
                current_time = time.time()
                queue_length = self.get_queue_length()
                actual_worker_count = self.get_worker_stats()
                
                metrics = {
                    "timestamp": current_time,
                    "queue_length": queue_length,
                    "worker_count": actual_worker_count,
                    "min_workers": self.worker_min_count,
                    "max_workers": self.worker_max_count
                }
                
                self.redis_client.hmset(self.metric_key, metrics)
                
                if current_time - self.last_scaling_time < 60:
                    logger.debug("Cooling down after recent scaling operation")
                    time.sleep(self.scaling_interval)
                    continue
                
                self.check_and_apply_scaling(queue_length, actual_worker_count)
                    
            except Exception as e:
                logger.error(f"Error in scaling monitor loop: {str(e)}")
                
            time.sleep(self.scaling_interval) 