#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
from pathlib import Path
import time

def build_docker():
    cmd = ["docker-compose", "build", "api-service", "worker", "test"]
    print(f"Building Docker images...")
    return subprocess.call(cmd)

def start_services():
    cmd = ["docker-compose", "up", "-d", "api-service", "worker", "redis"]
    print(f"Starting services...")
    result = subprocess.call(cmd)
    
    if result == 0:
        print("Waiting for services to initialize...")
        time.sleep(10)
    
    return result

def stop_services():
    cmd = ["docker-compose", "down"]
    print(f"Stopping services...")
    return subprocess.call(cmd)

def run_unit_tests(verbose=True, test_type=None, markers=None):
    cmd = ["docker-compose", "--profile", "test", "run", "--rm", "test", "python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if test_type:
        cmd.append(f"tests/{test_type}")
    
    if markers:
        cmd.append(f"-m {markers}")
    
    print(f"Running unit tests...")
    return subprocess.call(cmd)

def run_single_file_test(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        return 1
        
    file_abs_path = os.path.abspath(file_path)
    file_name = os.path.basename(file_path)
    
    cmd = [
        "docker-compose", "--profile", "test", "run", "--rm",
        "-e", f"TEST_FILE={file_name}",
        "-v", f"{file_abs_path}:/app/test_file",
        "test",
        "python", "-c", 
        f"import requests; "
        f"f = open('/app/test_file', 'rb'); "
        f"resp = requests.post('http://api-service:5000/classify_file', "
        f"files={{'file': ('{file_name}', f, 'application/octet-stream')}}); "
        f"task_id = resp.json()['task_id']; "
        f"print(f'Started classification task: {{task_id}}'); "
        f"import time; "
        f"for _ in range(60): "
        f"    r = requests.get(f'http://api-service:5000/classification/{{task_id}}'); "
        f"    s = r.json()['status']; "
        f"    if s in ['completed', 'failed']: "
        f"        print(f'Result: {{r.json()}}'); "
        f"        break; "
        f"    time.sleep(1); "
    ]
    
    return subprocess.call(cmd)

def run_load_test(concurrent=5, duration=30, files_dir="files"):
    cmd = [
        "docker-compose", "--profile", "test", "run", "--rm", "test", 
        "python", "tests/load/test_load.py",
        "--files-dir", files_dir,
        "--concurrent", str(concurrent), 
        "--duration", str(duration)
    ]
    
    print(f"Running load test with {concurrent} concurrent users for {duration} seconds...")
    return subprocess.call(cmd)

def main():
    parser = argparse.ArgumentParser(description="Test runner for file classification service")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    build_parser = subparsers.add_parser("build", help="Build Docker images")
    
    test_parser = subparsers.add_parser("test", help="Run tests on a specific file")
    test_parser.add_argument("file", nargs="?", help="File path to test classification")
    
    unit_parser = subparsers.add_parser("unit", help="Run unit and integration tests")
    unit_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    unit_parser.add_argument("--api-only", action="store_true", help="Run only API tests")
    unit_parser.add_argument("--services-only", action="store_true", help="Run only service tests")
    unit_parser.add_argument("--integration-only", action="store_true", help="Run only integration tests")
    unit_parser.add_argument("--markers", type=str, help="Pytest markers to filter tests")
    
    load_parser = subparsers.add_parser("load", help="Run load tests")
    load_parser.add_argument("--files-dir", type=str, default="files", help="Directory containing test files")
    load_parser.add_argument("--concurrent", type=int, default=5, help="Number of concurrent uploads")
    load_parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    
    services_parser = subparsers.add_parser("services", help="Manage Docker services")
    services_parser.add_argument("action", choices=["start", "stop"], help="Action to perform on services")
    
    args = parser.parse_args()
    
    if args.command == "build":
        return build_docker()
    
    elif args.command == "test":
        if args.file:
            if start_services() != 0:
                return 1
            return run_single_file_test(args.file)
        else:
            print("Error: No file specified for testing")
            return 1
    
    elif args.command == "unit":
        if start_services() != 0:
            return 1
            
        test_type = None
        if args.api_only:
            test_type = "api"
        elif args.services_only:
            test_type = "services"
        elif args.integration_only:
            test_type = "integration"
            
        return run_unit_tests(args.verbose, test_type, args.markers)
    
    elif args.command == "load":
        if start_services() != 0:
            return 1
        return run_load_test(args.concurrent, args.duration, args.files_dir)
    
    elif args.command == "services":
        if args.action == "start":
            return start_services()
        elif args.action == "stop":
            return stop_services()
    
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 