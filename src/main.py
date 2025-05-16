from fastapi import FastAPI, UploadFile, File, HTTPException, Path, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn
import os
import logging
import uuid
import redis.exceptions
from src.services.message_broker import MessageBroker
from src.models.response_models import ClassificationTaskResponse, ClassificationStatusResponse

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

MAX_FILE_SIZE = 50 * 1024 * 1024 
ALLOWED_FILE_EXTENSIONS = ['.pdf', '.docx', '.xlsx', '.jpg', '.jpeg', '.png', '.txt']

message_broker = MessageBroker()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

@app.exception_handler(redis.exceptions.ConnectionError)
async def redis_connection_exception_handler(request: Request, exc: redis.exceptions.ConnectionError):
    logger.error(f"Redis connection error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Classification service temporarily unavailable. Please try again later."},
    )

@app.post("/classify_file", response_model=ClassificationTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_classification(file: UploadFile = File(...)):
    """
    Start an asynchronous file classification task.
    Returns a task ID that can be used to retrieve results later.
    """
    temp_file_path = None
    try:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_FILE_EXTENSIONS)}"
            )

        content = await file.read()
        file_size = len(content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024 * 1024)} MB"
            )
        
        await file.seek(0)
        
        shared_temp_dir = os.path.join('files', 'temp')
        os.makedirs(shared_temp_dir, exist_ok=True)
        
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        temp_file_path = os.path.join(shared_temp_dir, unique_filename)
        
        with open(temp_file_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Saved temporary file to {temp_file_path}")
        
        try:
            task_id, _ = message_broker.send_classification_task(
                file_path=temp_file_path,
                filename=file.filename
            )
        except redis.exceptions.ConnectionError as e:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Classification service temporarily unavailable. Please try again later."
            )
        except Exception as e:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error scheduling classification task: {str(e)}"
            )
        
        logger.info(f"Started classification task: {task_id}")
        
        return ClassificationTaskResponse(
            task_id=task_id,
            filename=file.filename,
            status="pending"
        )
    except HTTPException:
        raise
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Removed temporary file {temp_file_path} after error")
            
        logger.error(f"Error starting classification: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/classification/{task_id}", response_model=ClassificationStatusResponse)
async def get_classification_status(task_id: str = Path(..., description="The task ID returned when starting classification")):
    """
    Get the status or result of a classification task.
    """
    if not task_id or not isinstance(task_id, str) or len(task_id) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task ID format"
        )
        
    try:
        status_data = message_broker.get_task_status(task_id)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Task with ID {task_id} not found or has expired"
            )
        
        return ClassificationStatusResponse(**status_data)
    except redis.exceptions.ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Classification service temporarily unavailable. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving task status: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    try:
        message_broker.redis_client.ping()
        return {"status": "healthy", "components": {"api": "up", "redis": "up"}}
    except redis.exceptions.ConnectionError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "components": {"api": "up", "redis": "down"}}
        )
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "unhealthy", "error": str(e)}
        )

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=5000, reload=True) 