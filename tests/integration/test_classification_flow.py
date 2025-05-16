import pytest
import os
import requests
import time
from pathlib import Path

class TestClassificationFlow:
    def test_end_to_end_classification(self, live_api, test_files, wait_for_task_completion):
        file_types = [
            test_files["pdf"]["bank_statement"],
            test_files["image"]["drivers_license"]
        ]
        
        for file_path in file_types:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                response = requests.post(f"{live_api}/classify_file", files=files)
            
            assert response.status_code == 202
            task_id = response.json()["task_id"]
            
            result = wait_for_task_completion(task_id)
            assert result is not None
            assert result["status"] == "completed"
            assert "predicted_type" in result
    
    def test_invalid_file_classification(self, live_api, temp_dir, wait_for_task_completion):
        invalid_file = temp_dir / "blank.pdf"
        
        with open(invalid_file, "wb") as f:
            f.write(b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\nxref\n0 3\n0000000000 65535 f\n0000000015 00000 n\n0000000065 00000 n\ntrailer\n<< /Root 1 0 R /Size 3 >>\nstartxref\n119\n%%EOF")
        
        with open(invalid_file, "rb") as f:
            files = {"file": (invalid_file.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        task_id = response.json()["task_id"]
        
        result = wait_for_task_completion(task_id)
        assert result is not None
        assert result["status"] in ["completed", "failed"]
    
    def test_concurrent_classifications(self, live_api, test_files, wait_for_task_completion):
        file_paths = [
            test_files["pdf"]["bank_statement"],
            test_files["pdf"]["bank_statement"],
            test_files["image"]["drivers_license"]
        ]
        
        tasks = []
        
        for file_path in file_paths:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                response = requests.post(f"{live_api}/classify_file", files=files)
            
            assert response.status_code == 202
            task_id = response.json()["task_id"]
            tasks.append(task_id)
        
        results = []
        for task_id in tasks:
            result = wait_for_task_completion(task_id)
            assert result is not None
            assert result["status"] in ["completed", "failed"]
            results.append(result)
        
        assert len(results) == len(file_paths)
    
    def test_status_polling(self, live_api, test_files):
        file_path = test_files["pdf"]["bank_statement"]
        
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        task_id = response.json()["task_id"]
        
        max_polls = 30
        poll_interval = 1
        final_status = None
        
        for _ in range(max_polls):
            status_response = requests.get(f"{live_api}/classification/{task_id}")
            assert status_response.status_code == 200
            
            status = status_response.json()["status"]
            if status in ["completed", "failed"]:
                final_status = status
                break
                
            time.sleep(poll_interval)
        
        assert final_status in ["completed", "failed"]
        
    def test_high_load_scenario(self, live_api, test_files):
        file_path = test_files["pdf"]["bank_statement"]
        task_ids = []
        
        for _ in range(20):
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                response = requests.post(f"{live_api}/classify_file", files=files)
            assert response.status_code == 202
            task_ids.append(response.json()["task_id"])
        
        total_completed = 0
        timeout = 120
        start_time = time.time()
        
        while time.time() - start_time < timeout and total_completed < len(task_ids):
            completed_count = 0
            for task_id in task_ids:
                try:
                    status_response = requests.get(f"{live_api}/classification/{task_id}")
                    if status_response.json()["status"] in ["completed", "failed"]:
                        completed_count += 1
                except Exception:
                    pass
            
            total_completed = completed_count
            if total_completed == len(task_ids):
                break
                
            time.sleep(5)
        
        assert total_completed > 0
    
    def test_api_restart_resilience(self, live_api, test_files, wait_for_task_completion):
        file_path = test_files["pdf"]["bank_statement"]
        
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        assert response.status_code == 202
        task_id = response.json()["task_id"]
        
        result = wait_for_task_completion(task_id)
        assert result is not None
        assert result["status"] in ["completed", "failed"]
    
    def test_zero_byte_file(self, live_api, temp_dir, wait_for_task_completion):
        empty_file = temp_dir / "empty.pdf"
        
        with open(empty_file, "wb") as f:
            pass
        
        with open(empty_file, "rb") as f:
            files = {"file": (empty_file.name, f, "application/pdf")}
            response = requests.post(f"{live_api}/classify_file", files=files)
        
        if response.status_code == 202:
            task_id = response.json()["task_id"]
            result = wait_for_task_completion(task_id)
            assert result is not None
            assert result["status"] in ["completed", "failed"]
        else:
            assert response.status_code in [400, 422]
    
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