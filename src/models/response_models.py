from pydantic import BaseModel
from typing import Optional, Literal, Dict

class ClassificationTaskResponse(BaseModel):
    task_id: str
    filename: str
    status: str
    
class ClassificationStatusResponse(BaseModel):
    task_id: str
    filename: str
    status: Literal["pending", "processing", "completed", "failed"]
    predicted_type: Optional[str] = None
    success: Optional[bool] = None
    error: Optional[str] = None

class WorkerScalingStatusResponse(BaseModel):
    current_worker_count: float
    min_workers: float
    max_workers: float
    worker_count: float
    queue_length: float
    timestamp: float
    last_scaling_time: float 