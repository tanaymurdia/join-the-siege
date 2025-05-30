import os
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import time
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import classification_report, accuracy_score, f1_score
import torch
from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm
import re
import PyPDF2
import pdfplumber
import docx
import warnings
import pytesseract
from PIL import Image
import cv2
from concurrent.futures import ThreadPoolExecutor

try:
    import fasttext
    FASTTEXT_AVAILABLE = True
except ImportError:
    FASTTEXT_AVAILABLE = False
    print("Warning: FastText not available. Some features may be limited.")

warnings.filterwarnings('ignore')

class DocumentFeatureExtractor:
    def __init__(self, model_dir='model/saved_models'):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        print("Initializing document feature extractor...")
        self.tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        self.model = AutoModel.from_pretrained("distilbert-base-uncased")
        
        self.text_based_formats = {'.docx', '.txt', '.csv', '.html', '.json', '.xml'}
        self.image_based_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif'}
        
        try:
            pytesseract.get_tesseract_version()
            self.ocr_available = True
            print("Tesseract OCR available, version:", pytesseract.get_tesseract_version())
        except Exception as e:
            self.ocr_available = False
            print(f"Tesseract OCR not available: {e}")
            print("OCR features will be disabled")
        
    def needs_ocr(self, file_path):
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        
        if not self.ocr_available:
            return False
            
        if ext in self.image_based_formats:
            return True
            
        if ext == '.pdf':
            try:
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        if page.extract_text().strip():
                            return False  
                return True  
            except:
                return True  
                
        return False
    
    def extract_text_from_pdf(self, file_path):
        if self.needs_ocr(file_path):
            return self.extract_text_from_image(file_path)
            
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "".join([page.extract_text() or "" for page in pdf.pages])
                if text.strip():
                    return text
                    
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "".join([page.extract_text() or "" for page in reader.pages])
                return text
        except Exception as e:
            print(f"PDF extraction failed for {file_path}: {e}")
            return ""
    
    def extract_text_from_docx(self, file_path):
        try:
            doc = docx.Document(file_path)
            return " ".join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"Error extracting text from DOCX {file_path}: {e}")
            return ""
            
    def extract_text_from_image(self, file_path):
        if not self.ocr_available or not self.needs_ocr(file_path):
            return ""
            
        try:
            image = Image.open(file_path)
            
            orig_width, orig_height = image.size
            if max(orig_width, orig_height) > 2000:
                scale_factor = 2000 / max(orig_width, orig_height)
                image = image.resize((int(orig_width * scale_factor), int(orig_height * scale_factor)), Image.LANCZOS)
            
            text = pytesseract.image_to_string(image, config='--oem 1 --psm 3')
            if text.strip():
                return text
                
            print("First OCR pass produced no text, trying preprocessing...")
            img_cv = cv2.imread(str(file_path))
            if img_cv is None:
                return ""
                
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            
            temp_path = f"{file_path}_temp.jpg"
            cv2.imwrite(temp_path, thresh)
            
            text = pytesseract.image_to_string(Image.open(temp_path), config='--oem 1 --psm 3')
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            print("\n--- OCR EXTRACTED TEXT (SECOND PASS) ---")
            print(text[:500] + ("..." if len(text) > 500 else ""))
            print(f"Total characters: {len(text)}")
            print("--- END OF OCR TEXT ---\n")
                
            return text
                
        except Exception as e:
            print(f"OCR failed for {file_path}: {e}")
            return ""
    
    def extract_text_from_file(self, file_path):
        try:
            file_path = Path(file_path)
            ext = file_path.suffix.lower()
            
            if ext == '.pdf':
                return self.extract_text_from_pdf(file_path)
            elif ext == '.docx':
                return self.extract_text_from_docx(file_path)
            elif ext in self.image_based_formats:
                return self.extract_text_from_image(file_path)
            elif ext == '.txt':
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
                except Exception as e:
                    print(f"Error reading TXT file {file_path}: {e}")
                    return ""
            elif ext == '.csv':
                try:
                    df = pd.read_csv(file_path)
                    return " ".join([str(col) for col in df.columns]) + " " + \
                        " ".join([str(val) for val in df.values.flatten() if str(val) != 'nan'])
                except Exception as e:
                    print(f"Error reading CSV file {file_path}: {e}")
                    return ""
            else:
                return ""
        except Exception as e:
            print(f"Unexpected error extracting text from {file_path}: {e}")
            return ""
    
    def get_bert_embeddings(self, text, max_length=512):
        if not text:
            return np.zeros(768)
            
        text = str(text)[:5000]  
        
        try:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=max_length)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
            
            embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
            return embeddings
        except Exception as e:
            print(f"Error generating BERT embeddings: {e}")
            return np.zeros(768)

class AdvancedFileClassifier:
    def __init__(self, model_dir='model/saved_models'):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.feature_extractor = DocumentFeatureExtractor(model_dir)
        self.classifier = None
        self.label_encoder = None
        self.max_workers = min(os.cpu_count() or 4, 8) 
    
    def _process_file(self, row):
        try:
            file_features = {}
            
            if 'path' in row and os.path.exists(row['path']):
                content = self.feature_extractor.extract_text_from_file(row['path'])
                content_embedding = self.feature_extractor.get_bert_embeddings(content)
                
                for i, val in enumerate(content_embedding):
                    file_features[f'content_emb_{i}'] = val
                
                from model.core.data_generator import SyntheticDataGenerator
                generator = SyntheticDataGenerator()
                doc_types = generator.document_types
                
                content_lower = content.lower()
                
                for doc_type, type_info in doc_types.items():
                    keywords = type_info["keywords"]
                    match_count = 0
                    unique_matches = set()
                    
                    for keyword in keywords:
                        keyword_lower = keyword.lower()
                        occurrences = content_lower.count(keyword_lower)
                        if occurrences > 0:
                            match_count += occurrences
                            unique_matches.add(keyword_lower)
                    
                    file_features[f'keyword_count_{doc_type}'] = match_count * 50.0  
                    file_features[f'keyword_unique_{doc_type}'] = len(unique_matches) * 100.0  
                    file_features[f'keyword_density_{doc_type}'] = (match_count / max(1, len(content.split()))) * 500.0  
                
                if 'content' not in row or not row['content']:
                    file_features['extracted_content'] = content
            else:
                for i in range(768):
                    file_features[f'content_emb_{i}'] = 0
                    
                from model.core.data_generator import SyntheticDataGenerator
                generator = SyntheticDataGenerator()
                doc_types = generator.document_types
                for doc_type in doc_types:
                    file_features[f'keyword_count_{doc_type}'] = 0.0
                    file_features[f'keyword_unique_{doc_type}'] = 0.0
                    file_features[f'keyword_density_{doc_type}'] = 0.0
            
            return file_features
        except Exception as e:
            print(f"Error processing file {row.get('path', 'unknown')}: {e}")
            empty_features = {}
            for i in range(768):
                empty_features[f'content_emb_{i}'] = 0
                
            from model.core.data_generator import SyntheticDataGenerator
            generator = SyntheticDataGenerator()
            doc_types = generator.document_types
            for doc_type in doc_types:
                empty_features[f'keyword_count_{doc_type}'] = 0.0
                empty_features[f'keyword_unique_{doc_type}'] = 0.0
                empty_features[f'keyword_density_{doc_type}'] = 0.0
            
            return empty_features
    
    def _extract_features(self, data):
        features = []
        
        if len(data) < 10:
            for _, row in tqdm(data.iterrows(), total=len(data), desc="Extracting features"):
                features.append(self._process_file(row))
        else:
            print(f"Using {self.max_workers} threads for parallel processing")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for _, row in data.iterrows():
                    futures.append(executor.submit(self._process_file, row))
                
                for future in tqdm(futures, desc="Extracting features"):
                    features.append(future.result())
        
        return pd.DataFrame(features)
    
    def build_model(self):
        from model.core.data_generator import SyntheticDataGenerator
        generator = SyntheticDataGenerator()
        doc_types = generator.document_types
        
        embedding_features = [f'content_emb_{i}' for i in range(768)]
        keyword_count_features = [f'keyword_count_{doc_type}' for doc_type in doc_types]
        keyword_unique_features = [f'keyword_unique_{doc_type}' for doc_type in doc_types]
        keyword_density_features = [f'keyword_density_{doc_type}' for doc_type in doc_types]
        
        content_pipeline = Pipeline([
            ('passthrough', FunctionTransformer())
        ])
        
        keyword_pipeline = Pipeline([
            ('passthrough', FunctionTransformer())
        ])
        
        feature_engineering = ColumnTransformer([
            ('content_embeddings', content_pipeline, embedding_features),
            ('keyword_counts', keyword_pipeline, keyword_count_features),
            ('keyword_unique', keyword_pipeline, keyword_unique_features),
            ('keyword_density', keyword_pipeline, keyword_density_features)
        ])
        
        model = Pipeline([
            ('features', feature_engineering),
            ('classifier', GradientBoostingClassifier(n_estimators=300, learning_rate=0.1, max_depth=5, random_state=42))
        ])
        
        return model
    
    def train(self, data, test_size=0.2, random_state=42):
        if 'filename' in data.columns:
            print("Warning: 'filename' found in training data but will be ignored")
            data = data.drop(columns=['filename'])
            
        features_df = self._extract_features(data)
        
        X_train, X_test, y_train, y_test = train_test_split(
            features_df, 
            data['type'],
            test_size=test_size,
            random_state=random_state,
            stratify=data['type']
        )
        
        print(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")
        
        model = self.build_model()
        
        print("Training model...")
        start_time = time.time()
        model.fit(X_train, y_train)
        training_time = time.time() - start_time
        print(f"Model trained in {training_time:.2f} seconds")
        
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='weighted')
        
        print(f"Model accuracy: {accuracy:.4f}")
        print(f"Model F1 score: {f1:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred))
        
        self.classifier = model
        
        return {
            'accuracy': accuracy,
            'f1_score': f1,
            'training_time': training_time
        }
    
    def save_model(self, filename='classifier_model.pkl'):
        if self.classifier:
            with open(self.model_dir / filename, 'wb') as f:
                pickle.dump(self.classifier, f)
            print(f"Model saved to {self.model_dir / filename}")
        else:
            print("No model to save. Train the model first.")
    
    def load_model(self, filename='classifier_model.pkl'):
        model_path = self.model_dir / filename
        if model_path.exists():
            with open(model_path, 'rb') as f:
                self.classifier = pickle.load(f)
            print(f"Model loaded from {model_path}")
            return True
        else:
            print(f"Model file {model_path} not found")
            return False
    
    def predict(self, file_path=None, file_obj=None, filename=None, extension=None):
        start_time = time.time()
        print(f"Predicting file: {file_path}, {file_obj}, {filename}, {extension}")
        try:
            if self.classifier is None:
                if not self.load_model():
                    raise ValueError("No classifier model available. Train or load a model first.")
            
            if file_path is None and file_obj is not None:
                temp_path = f"/tmp/temp_file_{int(time.time())}"
                with open(temp_path, 'wb') as f:
                    f.write(file_obj.read())
                file_path = temp_path
            
            data = pd.DataFrame([{
                'path': file_path
            }])
            
            content = self.feature_extractor.extract_text_from_file(file_path)
            
            keyword_prediction = None
            keyword_confidence = 0
            highest_score = 0
            
            if content.strip():
                from model.core.data_generator import SyntheticDataGenerator
                generator = SyntheticDataGenerator()
                doc_types = generator.document_types
                
                type_scores = {}
                for doc_type, type_info in doc_types.items():
                    keywords = type_info["keywords"]
                    matches = []
                    for keyword in keywords:
                        keyword_lower = keyword.lower()
                        content_lower = content.lower()
                        if keyword_lower in content_lower:
                            matches.append(keyword)
                    
                    score = len(matches)
                    type_scores[doc_type] = {"score": score, "matches": matches}
                
                sorted_scores = sorted(type_scores.items(), key=lambda x: x[1]["score"], reverse=True)
                
                for doc_type, info in sorted_scores:
                    if info["score"] > 0:                        
                        if info["score"] > highest_score:
                            highest_score = info["score"]
                            keyword_prediction = doc_type
                            if len(sorted_scores) > 1 and sorted_scores[1][1]["score"] > 0:
                                keyword_confidence = info["score"] / (info["score"] + sorted_scores[1][1]["score"])
                            else:
                                keyword_confidence = 1.0
                            
            features = self._extract_features(data)
            
            if hasattr(self.classifier, 'feature_names_in_'):                
                if 'filename_length' in self.classifier.feature_names_in_:
                    if filename:
                        features['filename_length'] = len(filename)
                    else:
                        features['filename_length'] = 0
                        
                if 'extension' in self.classifier.feature_names_in_:
                    if extension:
                        features['extension'] = str(extension).lower()
                    else:
                        features['extension'] = 'unknown'
                        
                if 'filename_words' in self.classifier.feature_names_in_:
                    if filename:
                        words = ' '.join(re.findall(r'\w+', filename)).lower()
                        features['filename_words'] = words
                    else:
                        features['filename_words'] = ''
                
                for feature in self.classifier.feature_names_in_:
                    if feature not in features and feature.startswith('extension_'):
                        features[feature] = '0'
                    if feature not in features:
                        print(f"Adding missing feature: {feature}")
                        features[feature] = '0'
            
            model_prediction = self.classifier.predict(features)[0]
            
            final_prediction = model_prediction
            
            if keyword_prediction and highest_score >= 3:
                if keyword_confidence > 0.65 and keyword_prediction != model_prediction:
                    final_prediction = keyword_prediction
            
            if file_obj and file_path.startswith("/tmp/"):
                try:
                    os.remove(file_path)
                except:
                    pass
                    
            processing_time = time.time() - start_time
            print(f"Classification completed in {processing_time:.2f} seconds")
            
            return final_prediction
        except Exception as e:
            print(f"Error during prediction: {e}")
            return "unknown_file"

if __name__ == "__main__":
    from model.core.data_generator import SyntheticDataGenerator
    
    print("Generating synthetic training data...")
    generator = SyntheticDataGenerator(output_dir="files/synthetic")
    dataset = generator.generate_dataset(num_samples=1000)
    
    print("Training model...")
    classifier = AdvancedFileClassifier()
    results = classifier.train(dataset)
    
    classifier.save_model()
    
    print("Model training complete.") 