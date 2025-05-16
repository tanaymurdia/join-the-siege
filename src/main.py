from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import io
import os
import tempfile
import logging
import uuid
from src.services.message_broker import MessageBroker
from src.models.response_models import ClassificationResponse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('api')
logging.getLogger('message_broker').setLevel(logging.INFO)
logging.getLogger('uvicorn').setLevel(logging.INFO)
logging.getLogger('fastapi').setLevel(logging.INFO)

app = FastAPI(
    title="File Classification API",
    description="API for classifying files using content-based analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

message_broker = MessageBroker()

@app.post("/classify_file", response_model=ClassificationResponse)
async def classify_file(file: UploadFile = File(...)):
    """
    Classify a file based on its content.
    """
    temp_file_path = None
    try:
        await file.seek(0)
        content = await file.read()
        
        shared_temp_dir = os.path.join('files', 'temp')
        os.makedirs(shared_temp_dir, exist_ok=True)
        
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        temp_file_path = os.path.join(shared_temp_dir, unique_filename)
        
        with open(temp_file_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Saved temporary file to {temp_file_path}")
        
        task_id, result_queue = message_broker.send_classification_task(
            file_path=temp_file_path,
            filename=file.filename
        )
        
        logger.info(f"Sent classification task to queue: {task_id}")
        
        result = message_broker.get_classification_result(
            result_queue=result_queue,
            timeout=60
        )
        
        if result is None:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"Removed temporary file {temp_file_path} after timeout")
                
            raise HTTPException(
                status_code=504, 
                detail="Classification request timed out"
            )
        
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Removed temporary file {temp_file_path}")
        
        return ClassificationResponse(
            filename=file.filename,
            predicted_type=result['predicted_type'],
            success=result['success'],
            error=result.get('error')
        )
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Removed temporary file {temp_file_path} after error")
            
        logger.error(f"Error classifying file: {str(e)}")
            
        return ClassificationResponse(
            filename=file.filename,
            predicted_type="unknown",
            success=False,
            error=str(e)
        )

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=5000, reload=True) 