import argparse
import os
import subprocess
import sys
from pathlib import Path
import random
import time


class DockerManager:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.parent.absolute()
        self.docker_dir = Path(__file__).parent.parent / "docker"
        self.docker_compose_file = self.docker_dir / "docker-compose.yml"
        self.container_name = "file-classifier"
        
    def build_image(self):
        print("Building the Docker image for file classifier...")
        cmd = [
            "docker-compose", 
            "-f", str(self.docker_compose_file), 
            "build"
        ]
        result = subprocess.run(cmd, cwd=str(self.root_dir))
        
        if result.returncode == 0:
            print("Docker image built successfully.")
            return True
        else:
            print("Failed to build Docker image.")
            return False
    
    def generate_data(self, num_samples=1000, poorly_named_ratio=0.3):
        print(f"Generating {num_samples} synthetic data samples (poorly named ratio: {poorly_named_ratio})...")
        cmd = [
            "docker-compose",
            "-f", str(self.docker_compose_file),
            "run",
            "--rm",
            self.container_name,
            "-m", "model.core.data_generator",
            "--output-dir", "/app/files/synthetic",
            "--num-samples", str(num_samples),
            "--poorly-named-ratio", str(poorly_named_ratio)
        ]
        
        result = subprocess.run(cmd, cwd=str(self.root_dir))
        
        if result.returncode == 0:
            print(f"Successfully generated {num_samples} synthetic data samples.")
            return True
        else:
            print("Failed to generate synthetic data.")
            return False
    
    def train_model(self, model_dir="/app/model/saved_models"):
        print("Training the classifier model on the synthetic data...")
        cmd = [
            "docker-compose",
            "-f", str(self.docker_compose_file),
            "run",
            "--rm",
            self.container_name,
            "-m", "model.core.train",
            "--model-dir", model_dir,
            "--output-dir", "/app/files/synthetic"
        ]
        
        result = subprocess.run(cmd, cwd=str(self.root_dir))
        
        if result.returncode == 0:
            print("Model training completed successfully.")
            return True
        else:
            print("Failed to train the model.")
            return False
            
    def test_classifier(self, file_path):
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} does not exist")
            return False
            
        file_path = os.path.abspath(file_path)
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        print(f"Testing classifier on file: {file_name} (using content only, filename ignored)")
        
        cmd = [
            "docker-compose",
            "-f", str(self.docker_compose_file),
            "run",
            "--rm",
            "-v", f"{dir_path}:/app/test_files",
            self.container_name,
            "-c", (
                f"from model.core.classifier_trainer import AdvancedFileClassifier; "
                f"classifier = AdvancedFileClassifier(); "
                f"prediction = classifier.predict(file_path='/app/test_files/{file_name}'); "
                f"print(f'Predicted class: {{prediction}} (based only on file content)')"
            )
        ]
        
        result = subprocess.run(cmd, cwd=str(self.root_dir))
        
        if result.returncode == 0:
            print("Classification completed successfully.")
            return True
        else:
            print("Classification failed.")
            return False
    
    def run_all(self, num_samples=1000, poorly_named_ratio=0.3, model_dir="/app/model/saved_models"):
        if self.build_image():
            if self.generate_data(num_samples, poorly_named_ratio):
                if self.train_model(model_dir):
                    print("All operations completed successfully.")
                    return True
        
        print("Some operations failed. Check the output above for details.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Manage Docker operations for file classifier")
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


if __name__ == "__main__":
    sys.exit(main()) 