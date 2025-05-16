import os
import time
import uuid
import requests
import concurrent.futures
import argparse
import numpy as np
from pathlib import Path

PLOTTING_ENABLED = False
try:
    import matplotlib.pyplot as plt
    PLOTTING_ENABLED = True
except ImportError:
    print("Warning: matplotlib not available. Plotting features disabled.")

API_URL = os.environ.get("API_URL", "http://localhost:5000")

def get_scaling_status():
    try:
        response = requests.get(f"{API_URL}/scaling/status")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting scaling status: {str(e)}")
        return None

def get_file_paths(test_files_dir):
    test_files_dir = Path(test_files_dir)
    if not test_files_dir.exists() or not test_files_dir.is_dir():
        raise ValueError(f"Test files directory {test_files_dir} does not exist")
        
    file_paths = []
    for ext in ['.pdf', '.docx', '.jpg', '.png', '.txt']:
        file_paths.extend(list(test_files_dir.glob(f"*{ext}")))
    
    if not file_paths:
        raise ValueError(f"No test files found in {test_files_dir}")
        
    return file_paths

def submit_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f)}
            response = requests.post(f"{API_URL}/classify_file", files=files)
            
        if response.status_code == 202:
            return response.json()["task_id"]
        else:
            print(f"Failed to submit file {file_path}: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Error submitting file {file_path}: {str(e)}")
        return None

def check_task_status(task_id):
    try:
        response = requests.get(f"{API_URL}/classification/{task_id}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error checking task status {task_id}: {str(e)}")
        return None

def run_scaling_test(files_dir, num_files, batch_size, delay_between_batches=1.0):
    file_paths = get_file_paths(files_dir)
    
    actual_num_files = min(num_files, len(file_paths))
    if actual_num_files < num_files:
        print(f"Warning: Only {actual_num_files} files available (requested {num_files})")
    
    selected_files = np.random.choice(file_paths, actual_num_files, replace=True)
    
    task_ids = []
    task_start_times = {}
    task_completion_times = {}
    
    scaling_metrics = []
    
    print(f"Starting scaling test with {actual_num_files} files in batches of {batch_size}")
    
    for i in range(0, len(selected_files), batch_size):
        batch = selected_files[i:i+batch_size]
        print(f"Submitting batch {i//batch_size + 1}/{(len(selected_files) + batch_size - 1)//batch_size}")
        
        batch_start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = {executor.submit(submit_file, file_path): file_path for file_path in batch}
            
            for future in concurrent.futures.as_completed(futures):
                file_path = futures[future]
                try:
                    task_id = future.result()
                    if task_id:
                        task_ids.append(task_id)
                        task_start_times[task_id] = time.time()
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
        
        scaling_data = get_scaling_status()
        if scaling_data:
            scaling_metrics.append({
                "timestamp": time.time(),
                "batch": i//batch_size + 1,
                "worker_count": scaling_data["worker_count"],
                "queue_length": scaling_data["queue_length"]
            })
        
        batch_duration = time.time() - batch_start
        print(f"Batch submitted in {batch_duration:.2f} seconds")
        
        if i + batch_size < len(selected_files) and delay_between_batches > 0:
            time.sleep(delay_between_batches)
    
    max_wait_time = 300  
    waiting_start = time.time()
    
    print(f"Waiting for {len(task_ids)} tasks to complete...")
    
    while task_ids and time.time() - waiting_start < max_wait_time:
        completed_tasks = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_task_status, task_id): task_id for task_id in task_ids[:20]}
            
            for future in concurrent.futures.as_completed(futures):
                task_id = futures[future]
                try:
                    result = future.result()
                    if result and result["status"] in ["completed", "failed"]:
                        completed_tasks.append(task_id)
                        task_completion_times[task_id] = time.time()
                except Exception as e:
                    print(f"Error checking status for {task_id}: {str(e)}")
        
        for task_id in completed_tasks:
            if task_id in task_ids:
                task_ids.remove(task_id)
        
        if task_ids:
            scaling_data = get_scaling_status()
            if scaling_data:
                scaling_metrics.append({
                    "timestamp": time.time(),
                    "batch": "waiting",
                    "worker_count": scaling_data["worker_count"],
                    "queue_length": scaling_data["queue_length"]
                })
            
            print(f"Waiting for {len(task_ids)} more tasks to complete...")
            time.sleep(2)
    
    if task_ids:
        print(f"Warning: {len(task_ids)} tasks did not complete within the timeout period")
    
    processing_times = []
    for task_id, start_time in task_start_times.items():
        if task_id in task_completion_times:
            processing_times.append(task_completion_times[task_id] - start_time)
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    print(f"Test completed. {len(processing_times)} tasks processed with average time {avg_processing_time:.2f} seconds")
    
    if PLOTTING_ENABLED:
        plot_scaling_metrics(scaling_metrics)
    else:
        print_scaling_metrics(scaling_metrics)
    
    return {
        "num_files": num_files,
        "batch_size": batch_size,
        "completed_tasks": len(processing_times),
        "avg_processing_time": avg_processing_time,
        "scaling_metrics": scaling_metrics
    }

def print_scaling_metrics(metrics):
    if not metrics:
        print("No scaling metrics to record")
        return
    
    print("\nScaling Metrics Summary:")
    print("------------------------")
    print(f"Total data points: {len(metrics)}")
    
    worker_counts = [m["worker_count"] for m in metrics]
    queue_lengths = [m["queue_length"] for m in metrics]
    
    print(f"Initial worker count: {worker_counts[0]}")
    print(f"Final worker count: {worker_counts[-1]}")
    print(f"Max worker count: {max(worker_counts)}")
    print(f"Min worker count: {min(worker_counts)}")
    
    print(f"Initial queue length: {queue_lengths[0]}")
    print(f"Final queue length: {queue_lengths[-1]}")
    print(f"Max queue length: {max(queue_lengths)}")
    print(f"Min queue length: {min(queue_lengths)}")
    
    output_dir = Path("tests/load/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    with open(output_dir / f"scaling_test_data_{timestamp}.txt", "w") as f:
        f.write("Time,Worker Count,Queue Length\n")
        first_time = metrics[0]["timestamp"]
        for m in metrics:
            rel_time = m["timestamp"] - first_time
            f.write(f"{rel_time:.2f},{m['worker_count']},{m['queue_length']}\n")
    
    print(f"Scaling metrics raw data saved to tests/load/results/scaling_test_data_{timestamp}.txt")

def plot_scaling_metrics(metrics):
    if not metrics:
        print("No scaling metrics to plot")
        return
    
    if not PLOTTING_ENABLED:
        print_scaling_metrics(metrics)
        return
    
    timestamps = [m["timestamp"] for m in metrics]
    start_time = min(timestamps)
    relative_times = [(t - start_time) for t in timestamps]
    
    worker_counts = [m["worker_count"] for m in metrics]
    queue_lengths = [m["queue_length"] for m in metrics]
    
    plt.figure(figsize=(12, 6))
    
    plt.subplot(2, 1, 1)
    plt.plot(relative_times, worker_counts, 'b-', marker='o')
    plt.title('Worker Count Over Time')
    plt.ylabel('Worker Count')
    plt.grid(True)
    
    plt.subplot(2, 1, 2)
    plt.plot(relative_times, queue_lengths, 'r-', marker='o')
    plt.title('Queue Length Over Time')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Queue Length')
    plt.grid(True)
    
    plt.tight_layout()
    
    output_dir = Path("tests/load/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    plt.savefig(output_dir / f"scaling_test_{timestamp}.png")
    print(f"Scaling metrics plot saved to tests/load/results/scaling_test_{timestamp}.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test worker scaling with batch file uploads")
    parser.add_argument("--files-dir", default="tests/data/test_files", help="Directory containing test files")
    parser.add_argument("--num-files", type=int, default=50, help="Number of files to process")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of files per batch")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds to wait between batches")
    
    args = parser.parse_args()
    
    results = run_scaling_test(args.files_dir, args.num_files, args.batch_size, args.delay)
    print(f"Test results: {results}")

    output_dir = Path("tests/load/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    with open(output_dir / f"scaling_test_summary_{timestamp}.txt", "w") as f:
        f.write(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Number of Files: {results['num_files']}\n")
        f.write(f"Batch Size: {results['batch_size']}\n")
        f.write(f"Completed Tasks: {results['completed_tasks']}\n")
        f.write(f"Average Processing Time: {results['avg_processing_time']:.2f} seconds\n")
        f.write("\nScaling Metrics:\n")
        
        for i, metric in enumerate(results['scaling_metrics']):
            f.write(f"Time {i}: Workers={metric['worker_count']}, Queue={metric['queue_length']}\n") 