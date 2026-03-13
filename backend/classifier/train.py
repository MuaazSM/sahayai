import pandas as pd
import joblib
import os
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

def train_and_compare():
    # 1. FINAL PATH LOGIC
    # Always looks in backend/data/wearable_features.csv
    current_dir = os.path.dirname(__file__)
    data_path = os.path.normpath(os.path.join(current_dir, "..", "data", "wearable_features.csv"))

    print(f"🔍 Looking for data at: {data_path}")
    
    if not os.path.exists(data_path):
        print(f"❌ Error: {data_path} not found!")
        print("💡 FIX: Run 'python demo/generate_wearable_data.py' first.")
        return

    # 2. LOAD AND PREPARE DATA
    df = pd.read_csv(data_path)
    
    # Map text labels to integers for XGBoost compatibility
    if df['label'].dtype == 'object':
        class_map = {"normal": 0, "fall": 1, "wandering": 2, "distress": 3}
        df['label'] = df['label'].map(class_map)

    X = df.drop('label', axis=1)
    y = df['label']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 3. THE MODEL ZOO
    # We remove the deprecated 'use_label_encoder' to keep the logs clean
    models = {
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "Logistic Regression": LogisticRegression(max_iter=2000),
        "SVM": SVC(probability=True),
        "XGBoost": XGBClassifier(eval_metric='mlogloss')
    }

    best_model = None
    best_acc = 0
    winner_name = ""

    print("\n🛠️  TRAINING CLASSIFIERS...")
    print("-" * 45)

    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        
        # This will now show realistic decimals (e.g., 0.9754) instead of 1.0000
        print(f"✅ {name:20} | Accuracy: {acc:.4f}")

        if acc > best_acc:
            best_acc = acc
            best_model = model
            winner_name = name

    # 4. SAVE CHAMPION
    save_path = os.path.join(current_dir, "model.joblib")
    joblib.dump(best_model, save_path)
    
    print("-" * 45)
    print(f"🏆 WINNER: {winner_name} ({best_acc:.4f} accuracy)")
    print(f"💾 Champion brain saved to: {save_path}")

if __name__ == "__main__":
    train_and_compare()