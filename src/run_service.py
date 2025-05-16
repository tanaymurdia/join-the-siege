#!/usr/bin/env python3
"""
Service management script for building, starting, and stopping Docker containers.

Usage:
    python -m src.run_service build       # Build all service containers
    python -m src.run_service start       # Start all services
    python -m src.run_service stop        # Stop all services
    python -m src.run_service restart     # Restart all services
    python -m src.run_service status      # Check status of services
    python -m src.run_service logs        # View logs of all services
    python -m src.run_service scale <n>   # Scale worker service to n instances
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

class ServiceManager:
    def __init__(self):
        self.project_root = self._find_project_root()
        os.chdir(self.project_root)
        
    def _find_project_root(self):
        current_dir = Path.cwd()
        
        while current_dir != current_dir.parent:
            if (current_dir / "docker-compose.yml").exists():
                return current_dir
            current_dir = current_dir.parent
            
        return Path.cwd()
    
    def _run_command(self, cmd, description):
        print(f"{description}...")
        try:
            return subprocess.call(cmd) == 0
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def build(self):
        cmd = ["docker-compose", "build", "api-service", "worker"]
        return self._run_command(cmd, "Building service containers")
    
    def start(self):
        cmd = ["docker-compose", "up", "-d", "api-service", "worker", "redis"]
        success = self._run_command(cmd, "Starting services")
        
        if success:
            print("Waiting for services to initialize...")
            time.sleep(5)
            self.status()
        
        return success
    
    def stop(self):
        cmd = ["docker-compose", "down"]
        return self._run_command(cmd, "Stopping services")
    
    def restart(self):
        if self.stop():
            time.sleep(2)
            return self.start()
        return False
    
    def status(self):
        cmd = ["docker-compose", "ps"]
        return self._run_command(cmd, "Checking service status")
    
    def logs(self, service=None, follow=False):
        if service:
            cmd = ["docker-compose", "logs"]
            if follow:
                cmd.append("-f")
            cmd.append(service)
            return self._run_command(cmd, f"Viewing logs for {service}")
        else:
            cmd = ["docker-compose", "logs"]
            if follow:
                cmd.append("-f")
            return self._run_command(cmd, "Viewing logs for all services")
    
    def scale(self, worker_count):
        if not worker_count or worker_count < 1:
            print("Error: Worker count must be at least 1")
            return False
            
        cmd = ["docker-compose", "up", "-d", "--scale", f"worker={worker_count}"]
        return self._run_command(cmd, f"Scaling worker service to {worker_count} instances")


def main():
    parser = argparse.ArgumentParser(description="Service management for the file classification system")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    subparsers.add_parser("build", help="Build all service containers")
    subparsers.add_parser("start", help="Start all services")
    subparsers.add_parser("stop", help="Stop all services")
    subparsers.add_parser("restart", help="Restart all services")
    subparsers.add_parser("status", help="Check status of services")
    
    logs_parser = subparsers.add_parser("logs", help="View logs of services")
    logs_parser.add_argument("--service", "-s", type=str, help="Service name to view logs for")
    logs_parser.add_argument("--follow", "-f", action="store_true", help="Follow log output")
    
    scale_parser = subparsers.add_parser("scale", help="Scale worker service")
    scale_parser.add_argument("count", type=int, help="Number of worker instances")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    manager = ServiceManager()
    
    if args.command == "build":
        return 0 if manager.build() else 1
    elif args.command == "start":
        return 0 if manager.start() else 1
    elif args.command == "stop":
        return 0 if manager.stop() else 1
    elif args.command == "restart":
        return 0 if manager.restart() else 1
    elif args.command == "status":
        return 0 if manager.status() else 1
    elif args.command == "logs":
        return 0 if manager.logs(args.service, args.follow) else 1
    elif args.command == "scale":
        return 0 if manager.scale(args.count) else 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 