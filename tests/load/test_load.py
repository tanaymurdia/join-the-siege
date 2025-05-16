import argparse
import os
import time
import requests
import threading
import random
from pathlib import Path
import concurrent.futures
import json
from datetime import datetime

API_URL = os.environ.get("API_URL", "http://localhost:5000")

def get_test_files(files_dir):
    test_files = []
    
    for file_path in Path(files_dir).glob("**/*"):
        if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.docx', '.xlsx']:
            test_files.append(file_path)
    
    return test_files

def upload_file(file_path):
    start_time = time.time()
    task_id = None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/octet-stream')}
            response = requests.post(f"{API_URL}/classify_file", files=files)
        
        if response.status_code == 202:
            task_id = response.json().get('task_id')
            upload_time = time.time() - start_time
            return {
                'file': file_path.name,
                'task_id': task_id,
                'upload_time': upload_time,
                'status': 'success'
            }
        else:
            return {
                'file': file_path.name,
                'error': f"Upload failed with status {response.status_code}",
                'response': response.text,
                'status': 'failed'
            }
    except Exception as e:
        return {
            'file': file_path.name,
            'error': str(e),
            'status': 'failed'
        }

def check_task_status(task_id, max_wait=60):
    start_time = time.time()
    final_result = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_URL}/classification/{task_id}")
            
            if response.status_code == 200:
                status = response.json().get('status')
                
                if status in ['completed', 'failed']:
                    processing_time = time.time() - start_time
                    result = response.json()
                    result['processing_time'] = processing_time
                    return result
            
            time.sleep(1)
        except Exception as e:
            print(f"Error checking status for task {task_id}: {e}")
            time.sleep(1)
    
    return {
        'task_id': task_id,
        'status': 'timeout',
        'error': f"Task did not complete within {max_wait} seconds"
    }

def run_load_test(files_dir, num_concurrent, test_duration=None, repeat=1):
    test_files = get_test_files(files_dir)
    
    if not test_files:
        print(f"No suitable test files found in {files_dir}")
        return
    
    print(f"Found {len(test_files)} test files")
    
    results = {
        'start_time': datetime.now().isoformat(),
        'config': {
            'files_dir': str(files_dir),
            'num_concurrent': num_concurrent,
            'test_duration': test_duration,
            'repeat': repeat
        },
        'uploads': [],
        'tasks': []
    }
    
    start_time = time.time()
    total_uploads = 0
    
    try:
        health_response = requests.get(f"{API_URL}/health")
        if health_response.status_code != 200:
            print(f"API health check failed: {health_response.status_code}")
            return
        
        print(f"Starting load test with {num_concurrent} concurrent uploads")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            running = True
            futures = []
            
            while running:
                while len(futures) < num_concurrent:
                    file_path = random.choice(test_files)
                    future = executor.submit(upload_file, file_path)
                    futures.append(future)
                
                done, not_done = concurrent.futures.wait(
                    futures, 
                    timeout=0.1,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )
                
                for future in done:
                    try:
                        result = future.result()
                        results['uploads'].append(result)
                        total_uploads += 1
                        
                        if result['status'] == 'success':
                            threading.Thread(
                                target=lambda: results['tasks'].append(
                                    check_task_status(result['task_id'])
                                )
                            ).start()
                    except Exception as e:
                        print(f"Error processing result: {e}")
                    
                    futures.remove(future)
                
                elapsed = time.time() - start_time
                if test_duration and elapsed >= test_duration:
                    running = False
                elif total_uploads >= len(test_files) * repeat and repeat > 0:
                    running = False
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        elapsed_time = time.time() - start_time
        
        results['end_time'] = datetime.now().isoformat()
        results['total_elapsed_time'] = elapsed_time
        results['total_uploads'] = total_uploads
        
        time.sleep(5)
        
        successful_uploads = [u for u in results['uploads'] if u['status'] == 'success']
        failed_uploads = [u for u in results['uploads'] if u['status'] == 'failed']
        
        completed_tasks = [t for t in results['tasks'] if t.get('status') == 'completed']
        failed_tasks = [t for t in results['tasks'] if t.get('status') == 'failed']
        timeout_tasks = [t for t in results['tasks'] if t.get('status') == 'timeout']
        
        avg_upload_time = sum(u.get('upload_time', 0) for u in successful_uploads) / len(successful_uploads) if successful_uploads else 0
        avg_processing_time = sum(t.get('processing_time', 0) for t in completed_tasks) / len(completed_tasks) if completed_tasks else 0
        
        results['statistics'] = {
            'successful_uploads': len(successful_uploads),
            'failed_uploads': len(failed_uploads),
            'completed_tasks': len(completed_tasks),
            'failed_tasks': len(failed_tasks),
            'timeout_tasks': len(timeout_tasks),
            'uploads_per_second': total_uploads / elapsed_time if elapsed_time > 0 else 0,
            'avg_upload_time': avg_upload_time,
            'avg_processing_time': avg_processing_time
        }
        
        output_file = f"load_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nLoad test completed in {elapsed_time:.2f} seconds")
        print(f"Total uploads: {total_uploads}")
        print(f"Successful uploads: {len(successful_uploads)}")
        print(f"Failed uploads: {len(failed_uploads)}")
        print(f"Completed tasks: {len(completed_tasks)}")
        print(f"Failed tasks: {len(failed_tasks)}")
        print(f"Timeout tasks: {len(timeout_tasks)}")
        print(f"Uploads per second: {results['statistics']['uploads_per_second']:.2f}")
        print(f"Average upload time: {avg_upload_time:.2f} seconds")
        print(f"Average processing time: {avg_processing_time:.2f} seconds")
        print(f"Results saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load testing for the file classification API")
    parser.add_argument('--files-dir', type=str, default='files', help='Directory containing test files')
    parser.add_argument('--concurrent', type=int, default=5, help='Number of concurrent uploads')
    parser.add_argument('--duration', type=int, help='Test duration in seconds')
    parser.add_argument('--repeat', type=int, default=1, help='Number of times to repeat the file set (0 for infinite)')
    
    args = parser.parse_args()
    
    run_load_test(
        files_dir=args.files_dir,
        num_concurrent=args.concurrent,
        test_duration=args.duration,
        repeat=args.repeat
    ) 