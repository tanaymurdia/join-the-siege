from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import io
import os
import tempfile
# Fix imports for Docker compatibility
from src.services.classifier_service import ClassifierService
from src.models.response_models import ClassificationResponse

app = FastAPI(
    title="File Classification API",
    description="API for classifying files using content-based analysis",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier_service = ClassifierService()

@app.post("/classify_file", response_model=ClassificationResponse)
async def classify_file(file: UploadFile = File(...)):
    """
    Classify a file based on its content.
    """
    try:
        await file.seek(0)
        content = await file.read()
        
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_file_path, 'wb') as f:
            f.write(content)
        
        file_type = classifier_service.classify_file(temp_file_path)
        
        os.remove(temp_file_path)
        
        return ClassificationResponse(
            filename=file.filename,
            predicted_type=file_type,
            success=True
        )
    except Exception as e:
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
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