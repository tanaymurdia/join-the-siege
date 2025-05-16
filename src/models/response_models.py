from pydantic import BaseModel
from typing import Optional, Literal

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