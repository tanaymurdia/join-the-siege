import argparse
import os
import subprocess
import sys
from pathlib import Path
import random
import time


class DockerManager:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.absolute()
        self.docker_compose_file = self.root_dir / "model" / "docker-compose.yml"
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
            "-m", "model.data_generator",
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
            "-m", "model.train",
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
        
        print(f"Testing classifier on file: {file_name}")
        
        cmd = [
            "docker-compose",
            "-f", str(self.docker_compose_file),
            "run",
            "--rm",
            "-v", f"{dir_path}:/app/test_files",
            self.container_name,
            "-c", (
                f"from model.classifier_trainer import AdvancedFileClassifier; "
                f"classifier = AdvancedFileClassifier(); "
                f"prediction = classifier.predict(file_path='/app/test_files/{file_name}'); "
                f"print(f'Predicted class: {{prediction}}')"
            )
        ]
        
        result = subprocess.run(cmd, cwd=str(self.root_dir))
        
        if result.returncode == 0:
            print("Classification completed successfully.")
            return True
        else:
            print("Classification failed.")
            return False
            
    def run_benchmark(self, data_dir, num_files=5):
        if not os.path.exists(data_dir):
            print(f"Error: Directory {data_dir} does not exist")
            return False
            
        data_dir = os.path.abspath(data_dir)
        
        print(f"Running benchmark on files in {data_dir}")
        print("This will test OCR-selective processing on various file types")
        
        all_files = []
        for ext in ['.pdf', '.jpg', '.png', '.docx', '.txt']:
            files = list(Path(data_dir).glob(f"**/*{ext}"))
            if files:
                selected = random.sample(files, min(len(files), num_files))
                all_files.extend(selected)
        
        if not all_files:
            print(f"No suitable files found in {data_dir}")
            return False
            
        print(f"Testing classification on {len(all_files)} files...")
        
        cmd = [
            "docker-compose",
            "-f", str(self.docker_compose_file),
            "run",
            "--rm",
            "-v", f"{data_dir}:/app/benchmark_files",
            self.container_name,
            "-c", (
                f"from model.classifier_trainer import AdvancedFileClassifier; "
                f"import os; import time; "
                f"classifier = AdvancedFileClassifier(); "
                f"results = {{'pdf': [], 'image': [], 'docx': [], 'txt': []}}; "
                f"test_files = {[str(f.relative_to(data_dir)) for f in all_files]}; "
                f"for file in test_files: "
                f"    start = time.time(); "
                f"    ext = os.path.splitext(file)[1].lower(); "
                f"    needs_ocr = 'No'; "
                f"    if ext in ['.jpg', '.jpeg', '.png']: "
                f"        file_type = 'image'; "
                f"        needs_ocr = 'Yes'; "
                f"    elif ext == '.pdf': "
                f"        file_type = 'pdf'; "
                f"        if classifier.feature_extractor.needs_ocr('/app/benchmark_files/' + file): "
                f"            needs_ocr = 'Yes'; "
                f"    elif ext == '.docx': "
                f"        file_type = 'docx'; "
                f"    else: "
                f"        file_type = 'txt'; "
                f"    prediction = classifier.predict(file_path='/app/benchmark_files/' + file); "
                f"    duration = time.time() - start; "
                f"    results[file_type].append((file, prediction, duration, needs_ocr)); "
                f"    print(f'{{file}} ({{}}) - {{prediction}} in {{duration:.2f}}s (OCR: {{needs_ocr}})'); "
                f"print('\\nBenchmark Summary:'); "
                f"for file_type, type_results in results.items(): "
                f"    if type_results: "
                f"        avg_time = sum(r[2] for r in type_results) / len(type_results); "
                f"        print(f'{{file_type.upper()}}: Avg processing time: {{avg_time:.2f}}s for {{len(type_results)}} files'); "
            )
        ]
        
        result = subprocess.run(cmd, cwd=str(self.root_dir))
        
        if result.returncode == 0:
            print("Benchmark completed successfully.")
            return True
        else:
            print("Benchmark failed.")
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
    
    benchmark_parser = subparsers.add_parser("benchmark", help="Benchmark classifier performance on different file types")
    benchmark_parser.add_argument("data_dir", type=str, help="Directory containing files to benchmark")
    benchmark_parser.add_argument("--num-files", type=int, default=5, 
                               help="Number of files of each type to test (default: 5)")
    
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
    elif args.command == "benchmark":
        return 0 if manager.run_benchmark(args.data_dir, args.num_files) else 1
    elif args.command == "all":
        return 0 if manager.run_all(args.num_samples, args.poorly_named_ratio, args.model_dir) else 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 