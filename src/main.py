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
from src.services.worker_scaling import WorkerScalingService
from src.models.response_models import ClassificationTaskResponse, ClassificationStatusResponse, WorkerScalingStatusResponse
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('api')
logging.getLogger('message_broker').setLevel(logging.INFO)
logging.getLogger('worker_scaling').setLevel(logging.INFO)
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
scaling_service = WorkerScalingService(redis_client=message_broker.redis_client)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting worker scaling service")
    scaling_service.start_monitoring()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down worker scaling service")
    scaling_service.stop_monitoring()

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

@app.get("/scaling/status", response_model=WorkerScalingStatusResponse)
async def get_scaling_status():
    """
    Get the current status of worker scaling.
    """
    try:
        metrics = scaling_service.redis_client.hgetall(scaling_service.metric_key)
        
        if not metrics:
            metrics = {
                "current_worker_count": scaling_service.current_worker_count,
                "min_workers": scaling_service.worker_min_count,
                "max_workers": scaling_service.worker_max_count,
                "worker_count": scaling_service.get_worker_stats(),
                "queue_length": scaling_service.get_queue_length(),
                "timestamp": time.time(),
                "last_scaling_time": 0
            }
            
        for k in metrics:
            if k in ["timestamp", "last_scaling_time", "current_worker_count", 
                     "worker_count", "queue_length", "min_workers", "max_workers"]:
                metrics[k] = float(metrics[k])
                
        return WorkerScalingStatusResponse(**metrics)
    except redis.exceptions.ConnectionError:
        logger.warning("Redis connection error in get_scaling_status")
        return WorkerScalingStatusResponse(
            current_worker_count=scaling_service.current_worker_count,
            min_workers=scaling_service.worker_min_count,
            max_workers=scaling_service.worker_max_count,
            worker_count=scaling_service.get_worker_stats(),
            queue_length=scaling_service.get_queue_length(),
            timestamp=time.time(),
            last_scaling_time=0
        )
    except Exception as e:
        logger.error(f"Error getting scaling status: {str(e)}")
        return WorkerScalingStatusResponse(
            current_worker_count=scaling_service.current_worker_count,
            min_workers=scaling_service.worker_min_count,
            max_workers=scaling_service.worker_max_count,
            worker_count=scaling_service.get_worker_stats(),
            queue_length=scaling_service.get_queue_length(),
            timestamp=time.time(),
            last_scaling_time=0
        )

@app.post("/scaling/workers/{count}")
async def set_worker_count(count: int = Path(..., description="Target number of workers", ge=1, le=20)):
    """
    Manually set the number of worker instances.
    """
    try:
        scaling_service.scale_workers(count)
        return {"status": "success", "message": f"Worker count set to {count}"}
    except Exception as e:
        logger.error(f"Error setting worker count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting worker count: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    try:
        message_broker.redis_client.ping()
        worker_count = scaling_service.get_worker_stats()
        return {
            "status": "healthy" if worker_count > 0 else "degraded", 
            "components": {
                "api": "up", 
                "redis": "up",
                "workers": {
                    "status": "up" if worker_count > 0 else "down",
                    "count": worker_count
                }
            }
        }
    except redis.exceptions.ConnectionError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "components": {"api": "up", "redis": "down", "workers": {"status": "unknown", "count": 0}}}
        )
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        if "redis" in str(e).lower():
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "components": {"api": "up", "redis": "down", "workers": {"status": "unknown", "count": 0}}}
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"status": "unhealthy", "error": str(e)}
            )

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=5000, reload=True) 