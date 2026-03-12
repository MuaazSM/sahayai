# demo/train_classifier.py

import pandas as pd
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

def train_model():
    # 1. Load the data we just generated
    # We go up one folder from 'demo' to 'backend', then into 'data'
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    csv_path = os.path.join(backend_dir, "data", "wearable_features.csv")
    
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # 2. Separate features (X) and the answer key/labels (y)
    X = df.drop("label", axis=1)
    y = df["label"]
    
    # 3. Split into training data (80%) and testing data (20%)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 4. Create and train the Random Forest AI
    print("Training Random Forest Classifier...")
    # COST: $0.00 (Runs entirely on your machine using scikit-learn)
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    # 5. Test the AI to see how smart it is
    print("\nEvaluating Model Accuracy:")
    y_pred = clf.predict(X_test)
    print(classification_report(y_test, y_pred))
    
    # 6. Save the trained "brain" so Muaaz can use it in his API
    model_dir = os.path.join(backend_dir, "classifier")
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, "model.joblib")
    joblib.dump(clf, model_path)
    print(f"\n✅ AI Model successfully saved to {model_path}!")

if __name__ == "__main__":
    train_model()