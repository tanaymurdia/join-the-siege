import os
import sys
import logging
from pathlib import Path
from model.core.classifier_trainer import AdvancedFileClassifier

logger = logging.getLogger('classifier_service')

class ClassifierService:
    def __init__(self, model_dir='model/saved_models'):
        self.classifier = AdvancedFileClassifier(model_dir=model_dir)
        self.load_model()
        
    def load_model(self):
        success = self.classifier.load_model()
        if not success:
            logger.warning("Could not load the classifier model. Classification may not work properly.")
            
    def classify_file(self, file_path):
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File {file_path} does not exist")
            
        try:
            result = self.classifier.predict(file_path=file_path)
            return result
        except Exception as e:
            logger.error(f"Error classifying {file_path}: {str(e)}")
            raise
        
    def classify_file_object(self, file_obj):
        if file_obj is None:
            logger.error("File object is None")
            raise ValueError("File object cannot be None")
        
        filename = getattr(file_obj, 'name', None)
        extension = None
        
        if filename:
            _, extension = os.path.splitext(filename)
                    
        try:
            result = self.classifier.predict(
                file_obj=file_obj, 
                filename=filename,
                extension=extension
            )
            
            return result
        except Exception as e:
            logger.error(f"Error classifying {filename}: {str(e)}")
            raise 