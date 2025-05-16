import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from src.services.classifier_service import ClassifierService

class TestClassifierService:
    def test_file_not_found(self):
        classifier_service = ClassifierService()
        non_existent_file = "/path/to/non-existent-file.pdf"
        
        with pytest.raises(FileNotFoundError):
            classifier_service.classify_file(non_existent_file)
    
    def test_classify_none_file_object(self):
        classifier_service = ClassifierService()
        
        with pytest.raises(ValueError, match="File object cannot be None"):
            classifier_service.classify_file_object(None)
    
    @patch('model.core.classifier_trainer.AdvancedFileClassifier.predict')
    def test_classifier_error_handling(self, mock_predict):
        mock_predict.side_effect = Exception("Simulated classification error")
        classifier_service = ClassifierService()
        
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()
            
            with pytest.raises(Exception, match="Simulated classification error"):
                classifier_service.classify_file(temp_file.name)
    
    @patch('model.core.classifier_trainer.AdvancedFileClassifier.predict')
    def test_unsupported_file_extension(self, mock_predict):
        mock_predict.side_effect = Exception("Unsupported file extension")
        classifier_service = ClassifierService()
        
        with tempfile.NamedTemporaryFile(suffix=".unsupported") as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()
            
            with pytest.raises(Exception):
                classifier_service.classify_file(temp_file.name)
    
    @patch('model.core.classifier_trainer.AdvancedFileClassifier.predict')
    def test_corrupted_file_handling(self, mock_predict):
        mock_predict.side_effect = Exception("Unable to parse file content")
        classifier_service = ClassifierService()
        
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.write(b"This is not a valid PDF file")
            temp_file.flush()
            
            with pytest.raises(Exception):
                classifier_service.classify_file(temp_file.name)
    
    @patch('model.core.classifier_trainer.AdvancedFileClassifier.load_model')
    def test_model_load_failure(self, mock_load_model):
        mock_load_model.return_value = False
        
        with patch('logging.Logger.warning') as mock_warning:
            classifier_service = ClassifierService()
            mock_warning.assert_called_with("Could not load the classifier model. Classification may not work properly.")
            
    @patch('model.core.classifier_trainer.AdvancedFileClassifier.predict')
    def test_empty_file_handling(self, mock_predict):
        mock_predict.side_effect = Exception("Empty file content")
        classifier_service = ClassifierService()
        
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.flush()
            
            with pytest.raises(Exception):
                classifier_service.classify_file(temp_file.name) 