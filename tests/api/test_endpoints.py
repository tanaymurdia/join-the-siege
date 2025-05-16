import pytest
import os
import requests
from pathlib import Path

class TestHealthEndpoint:
    def test_health_check(self, live_api):
        response = requests.get(f"{live_api}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["components"]["api"] == "up"
        assert response.json()["components"]["redis"] == "up"

class TestClassifyFileEndpoint:
    def test_classify_file_success(self, live_api, test_files):
        file_path = test_files["pdf"]["bank_statement"]
        
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        assert "task_id" in response.json()
        assert response.json()["status"] == "pending"
        assert response.json()["filename"] == file_path.name
    
    def test_file_type_validation(self, live_api, temp_dir):
        invalid_file = temp_dir / "test.xyz"
        
        with open(invalid_file, "w") as f:
            f.write("test content")
            
        with open(invalid_file, "rb") as f:
            files = {"file": (invalid_file.name, f, "application/octet-stream")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 415
        assert "Unsupported file type" in response.json()["detail"]
    
    def test_file_size_limit(self, live_api, temp_dir):
        large_file = temp_dir / "too_large.pdf"
        
        with open(large_file, "wb") as f:
            f.write(b"0" * (51 * 1024 * 1024)) 
            
        with open(large_file, "rb") as f:
            files = {"file": (large_file.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]
    
    def test_missing_file(self, live_api):
        response = requests.post(f"{live_api}/classify_file")
        assert response.status_code == 422  
    
    def test_empty_file(self, live_api, temp_dir):
        empty_file = temp_dir / "empty.pdf"
        
        with open(empty_file, "wb") as f:
            pass
            
        with open(empty_file, "rb") as f:
            files = {"file": (empty_file.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        
        task_id = response.json()["task_id"]
        for _ in range(30):
            status_response = requests.get(f"{live_api}/classification/{task_id}")
            if status_response.json()["status"] in ["completed", "failed"]:
                break
            import time
            time.sleep(1)
    
    def test_corrupt_file(self, live_api, temp_dir):
        corrupt_file = temp_dir / "corrupt.pdf"
        
        with open(corrupt_file, "wb") as f:
            f.write(b"This is not a valid PDF file content")
            
        with open(corrupt_file, "rb") as f:
            files = {"file": (corrupt_file.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        
        task_id = response.json()["task_id"]
        for _ in range(30):
            status_response = requests.get(f"{live_api}/classification/{task_id}")
            if status_response.json()["status"] in ["completed", "failed"]:
                assert status_response.json()["status"] == "failed" or "error" in status_response.json()
                break
            import time
            time.sleep(1)
    
    def test_concurrent_requests(self, live_api, test_files):
        file_path = test_files["pdf"]["bank_statement"]
        task_ids = []
        
        for _ in range(5):
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/pdf")}
                response = requests.post(f"{live_api}/classify_file", files=files)
            
            assert response.status_code == 202
            task_ids.append(response.json()["task_id"])
        
        assert len(task_ids) == 5
        assert len(set(task_ids)) == 5

class TestClassificationStatusEndpoint:
    def test_get_status_success(self, live_api, test_files, wait_for_task_completion):
        file_path = test_files["pdf"]["bank_statement"]
        
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        task_id = response.json()["task_id"]
        
        status_response = requests.get(f"{live_api}/classification/{task_id}")
        assert status_response.status_code == 200
        assert "status" in status_response.json()
        
        result = wait_for_task_completion(task_id)
        assert result is not None
        assert result["status"] in ["completed", "failed"]
    
    def test_invalid_task_id(self, live_api):
        response = requests.get(f"{live_api}/classification/invalid")
        assert response.status_code == 400
        assert "Invalid task ID format" in response.json()["detail"]
    
    def test_nonexistent_task_id(self, live_api):
        response = requests.get(f"{live_api}/classification/12345678-1234-1234-1234-123456789012")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        
    def test_task_status_transitions(self, live_api, test_files):
        file_path = test_files["pdf"]["bank_statement"]
        
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        task_id = response.json()["task_id"]
        
        observed_statuses = []
        for _ in range(60):
            status_response = requests.get(f"{live_api}/classification/{task_id}")
            current_status = status_response.json()["status"]
            
            if current_status not in observed_statuses:
                observed_statuses.append(current_status)
                
            if current_status in ["completed", "failed"]:
                break
                
            import time
            time.sleep(1)
        
        assert len(observed_statuses) >= 2 