import os
import sys
from pathlib import Path
# Fix import path for Docker compatibility
from model.classifier_trainer import AdvancedFileClassifier

class ClassifierService:
    def __init__(self, model_dir='model/saved_models'):
        self.classifier = AdvancedFileClassifier(model_dir=model_dir)
        self.load_model()
        
    def load_model(self):
        success = self.classifier.load_model()
        if not success:
            print("Warning: Could not load the classifier model. Classification may not work properly.")
            
    def classify_file(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} does not exist")
            
        result = self.classifier.predict(file_path=file_path)
        return result
        
    def classify_file_object(self, file_obj):
        if file_obj is None:
            raise ValueError("File object cannot be None")
        
        # Extract filename and extension from the file object
        filename = getattr(file_obj, 'name', None)
        extension = None
        
        if filename:
            # Extract extension including the dot (e.g. '.pdf')
            _, extension = os.path.splitext(filename)
            
        # Pass both the file object and filename details to the classifier
        result = self.classifier.predict(
            file_obj=file_obj, 
            filename=filename,
            extension=extension
        )
        
        return result 