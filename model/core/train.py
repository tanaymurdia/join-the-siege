import argparse
from pathlib import Path
import os
import pandas as pd

from model.core.data_generator import SyntheticDataGenerator
from model.core.classifier_trainer import AdvancedFileClassifier

def main():
    parser = argparse.ArgumentParser(description='Train and save the file classifier model')
    parser.add_argument('--samples', type=int, default=0,
                        help='Number of synthetic samples to generate for training (0 to use existing data)')
    parser.add_argument('--output-dir', type=str, default='files/synthetic',
                        help='Directory to save/load synthetic training data')
    parser.add_argument('--model-dir', type=str, default='model/saved_models',
                        help='Directory to save the trained model')
    parser.add_argument('--poorly-named-ratio', type=float, default=0.3,
                        help='Ratio of poorly named files in the synthetic dataset')
    
    args, _ = parser.parse_known_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_path = output_dir / "metadata.csv"
    
    if args.samples > 0:
        print(f"Generating {args.samples} synthetic training samples...")
        generator = SyntheticDataGenerator(output_dir=args.output_dir)
        dataset = generator.generate_dataset(
            num_samples=args.samples,
            poorly_named_ratio=args.poorly_named_ratio
        )
    elif metadata_path.exists():
        print(f"Loading existing dataset from {metadata_path}")
        dataset = pd.read_csv(metadata_path)
        print(f"Loaded {len(dataset)} samples")
    else:
        print(f"No metadata file found at {metadata_path}. Generating 1000 samples as fallback.")
        generator = SyntheticDataGenerator(output_dir=args.output_dir)
        dataset = generator.generate_dataset(num_samples=1000)
    
    print(f"Dataset distribution:\n{dataset['type'].value_counts()}")
    
    print("\nTraining model...")
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    
    classifier = AdvancedFileClassifier(model_dir=args.model_dir)
    results = classifier.train(dataset)
    
    classifier.save_model()
    
    print(f"\nModel training complete. Accuracy: {results['accuracy']:.4f}, F1 Score: {results['f1_score']:.4f}")
    print(f"Model saved to {Path(args.model_dir) / 'classifier_model.pkl'}")

if __name__ == "__main__":
    main() 