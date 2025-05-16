#!/usr/bin/env python
"""
Entry point for model operations. This script delegates to the appropriate Docker
operations based on the command.

Usage:
    python -m model.run build            
    python -m model.run generate-data    
    python -m model.run train            
    python -m model.run test <file_path> 
    python -m model.run all              
"""

import sys
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Run model operations in Docker")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    build_parser = subparsers.add_parser("build", help="Build the Docker image")
    
    data_parser = subparsers.add_parser("generate-data", help="Generate synthetic data")
    data_parser.add_argument("--num-samples", type=int, default=1000,
                           help="Number of synthetic samples to generate (default: 1000)")
    data_parser.add_argument("--poorly-named-ratio", type=float, default=0.3,
                           help="Ratio of poorly named files (default: 0.3)")
    
    train_parser = subparsers.add_parser("train", help="Train the classifier model")
    train_parser.add_argument("--model-dir", type=str, default="/app/model/saved_models",
                            help="Directory to save the trained model (default: /app/model/saved_models)")
    
    test_parser = subparsers.add_parser("test", help="Test the classifier on a file")
    test_parser.add_argument("file_path", type=str, help="Path to the file to classify")
    
    all_parser = subparsers.add_parser("all", help="Run all operations")
    all_parser.add_argument("--num-samples", type=int, default=1000,
                          help="Number of synthetic samples to generate (default: 1000)")
    all_parser.add_argument("--poorly-named-ratio", type=float, default=0.3,
                          help="Ratio of poorly named files (default: 0.3)")
    all_parser.add_argument("--model-dir", type=str, default="/app/model/saved_models",
                          help="Directory to save the trained model (default: /app/model/saved_models)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        from model.utils.docker_manager import DockerManager
        manager = DockerManager()
        
        if args.command == "build":
            return 0 if manager.build_image() else 1
        elif args.command == "generate-data":
            return 0 if manager.generate_data(args.num_samples, args.poorly_named_ratio) else 1
        elif args.command == "train":
            return 0 if manager.train_model(args.model_dir) else 1
        elif args.command == "test":
            return 0 if manager.test_classifier(args.file_path) else 1
        elif args.command == "all":
            return 0 if manager.run_all(args.num_samples, args.poorly_named_ratio, args.model_dir) else 1
        else:
            parser.print_help()
            return 1
    except ImportError as e:
        print(f"Import error: {e}")
        print("This likely means dependencies aren't installed. Run 'model.run build' first to build the Docker image.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 