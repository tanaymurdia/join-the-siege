from pydantic import BaseModel
from typing import Optional

class ClassificationResponse(BaseModel):
    filename: str
    predicted_type: str
    success: bool
    error: Optional[str] = None 