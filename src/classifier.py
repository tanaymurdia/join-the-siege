from werkzeug.datastructures import FileStorage
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from model.classifier_trainer import AdvancedFileClassifier

def classify_file(file: FileStorage):
    classifier = AdvancedFileClassifier()
    
    try:
        prediction = classifier.predict(file_obj=file)
        return prediction
    except Exception as e:
        print(f"Error classifying file: {e}")
        
        filename = file.filename.lower()
        
        if "drivers_license" in filename:
            return "drivers_license"

        if "bank_statement" in filename:
            return "bank_statement"

        if "invoice" in filename:
            return "invoice"

        return "unknown file"

