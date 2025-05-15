import os
import sys
import logging
from pathlib import Path
from model.classifier_trainer import AdvancedFileClassifier

logger = logging.getLogger('classifier_service')

class ClassifierService:
    def __init__(self, model_dir='model/saved_models'):
        logger.info(f"Initializing classifier service with model directory: {model_dir}")
        self.classifier = AdvancedFileClassifier(model_dir=model_dir)
        self.load_model()
        
    def load_model(self):
        logger.info("Loading classification model")
        success = self.classifier.load_model()
        if not success:
            logger.warning("Could not load the classifier model. Classification may not work properly.")
        else:
            logger.info("Classification model loaded successfully")
            
    def classify_file(self, file_path):
        logger.info(f"Classifying file: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File {file_path} does not exist")
            
        try:
            result = self.classifier.predict(file_path=file_path)
            logger.info(f"Classification result for {file_path}: {result}")
            return result
        except Exception as e:
            logger.error(f"Error classifying file {file_path}: {str(e)}")
            raise
        
    def classify_file_object(self, file_obj):
        if file_obj is None:
            logger.error("File object is None")
            raise ValueError("File object cannot be None")
        
        filename = getattr(file_obj, 'name', None)
        extension = None
        
        if filename:
            _, extension = os.path.splitext(filename)
            
        logger.info(f"Classifying file object with filename: {filename}")
        
        try:
            result = self.classifier.predict(
                file_obj=file_obj, 
                filename=filename,
                extension=extension
            )
            
            logger.info(f"Classification result for {filename}: {result}")
            return result
        except Exception as e:
            logger.error(f"Error classifying file object {filename}: {str(e)}")
            raise 