"""
SahayAI Wearable Classifier — Training Script
===============================================
Full ML pipeline:
  1. Load data from backend/data/wearable_features.csv
  2. Split into Train (60%) / Validation (20%) / Test (20%) — stratified
  3. Compare baseline models on validation set
  4. Hyperparameter tune the best model family using validation set
  5. Evaluate FINAL model on held-out test set (touched only once)
  6. Print classification report + confusion matrix + feature importances
  7. Save model as backend/classifier/model.joblib

Run:  python backend/classifier/train.py
Prereq:  python demo/generate_wearable_data.py
"""

import os
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

CLASS_NAMES = {0: "Normal", 1: "Fall", 2: "Wandering", 3: "Distress"}


def train_and_compare():
    # ==================================================================
    # 1. LOAD DATA
    # ==================================================================
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.normpath(os.path.join(current_dir, "..", "data", "wearable_features.csv"))

    print(f"Looking for data at: {data_path}")
    if not os.path.exists(data_path):
        print(f"ERROR: {data_path} not found!")
        print("FIX: Run 'python demo/generate_wearable_data.py' first.")
        return

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} samples with {len(df.columns)-1} features")

    if df["label"].dtype == "object":
        df["label"] = df["label"].map({"normal": 0, "fall": 1, "wandering": 2, "distress": 3})

    X = df.drop("label", axis=1)
    y = df["label"]

    # ==================================================================
    # 2. THREE-WAY SPLIT: Train 60% / Validation 20% / Test 20%
    #    Test set is touched ONCE at the very end for final evaluation.
    #    All model selection and tuning happens on train+val only.
    # ==================================================================
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.40, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )
    print(f"Train: {len(X_train)} | Validation: {len(X_val)} | Test: {len(X_test)}")
    print(f"Class distribution (train): {dict(y_train.value_counts().sort_index())}")

    # ==================================================================
    # 3. BASELINE COMPARISON on validation set
    #    We try multiple model families to pick the best starting point
    #    before hyperparameter tuning.
    # ==================================================================
    print("\n" + "=" * 58)
    print("  STAGE 1: BASELINE MODEL COMPARISON (on validation set)")
    print("=" * 58)

    baselines = {
        "Random Forest": RandomForestClassifier(
            n_estimators=100, random_state=42, n_jobs=-1
        ),
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, random_state=42))
        ]),
        "SVM (RBF)": Pipeline([
            ("scaler", StandardScaler()),
            ("svm", SVC(probability=True, random_state=42))
        ]),
    }

    try:
        from xgboost import XGBClassifier
        baselines["XGBoost"] = XGBClassifier(
            n_estimators=100, eval_metric="mlogloss",
            random_state=42, verbosity=0
        )
    except ImportError:
        print("  (XGBoost not installed — skipping)")

    baseline_scores = {}
    for name, model in baselines.items():
        model.fit(X_train, y_train)
        val_acc = accuracy_score(y_val, model.predict(X_val))
        train_acc = accuracy_score(y_train, model.predict(X_train))
        gap = train_acc - val_acc
        baseline_scores[name] = val_acc
        overfit_flag = " (overfit!)" if gap > 0.03 else ""
        print(f"  {name:25s} | val={val_acc:.4f}  train={train_acc:.4f}  gap={gap:.4f}{overfit_flag}")

    best_family = max(baseline_scores, key=baseline_scores.get)
    print(f"\n  Best baseline: {best_family} ({baseline_scores[best_family]:.4f})")

    # ==================================================================
    # 4. HYPERPARAMETER TUNING using GridSearchCV on train set,
    #    evaluated on validation set
    # ==================================================================
    print("\n" + "=" * 58)
    print("  STAGE 2: HYPERPARAMETER TUNING (GridSearchCV)")
    print("=" * 58)

    # We tune Random Forest since it's typically the winner on tabular data.
    # Also tune XGBoost if available. Pick whichever is better after tuning.
    tuned_models = {}

    # --- Random Forest tuning ---
    print("\n  Tuning Random Forest...")
    rf_grid = {
        "n_estimators": [100, 200],
        "max_depth": [10, 16, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 3],
    }
    rf_search = GridSearchCV(
        RandomForestClassifier(random_state=42, n_jobs=-1),
        rf_grid,
        cv=3,                       # 3-fold CV on train set
        scoring="accuracy",
        n_jobs=-1,
        verbose=0,
    )
    rf_search.fit(X_train, y_train)
    rf_val_acc = accuracy_score(y_val, rf_search.predict(X_val))
    print(f"  Best RF params: {rf_search.best_params_}")
    print(f"  RF CV score: {rf_search.best_score_:.4f} | Val score: {rf_val_acc:.4f}")
    tuned_models["Random Forest (tuned)"] = (rf_search.best_estimator_, rf_val_acc)

    # --- XGBoost tuning (if available) ---
    try:
        from xgboost import XGBClassifier
        print("\n  Tuning XGBoost...")
        xgb_grid = {
            "n_estimators": [100, 200],
            "max_depth": [6, 8],
            "learning_rate": [0.05, 0.1],
            "min_child_weight": [1, 3],
        }
        xgb_search = GridSearchCV(
            XGBClassifier(eval_metric="mlogloss", random_state=42, verbosity=0),
            xgb_grid,
            cv=3,
            scoring="accuracy",
            n_jobs=-1,
            verbose=0,
        )
        xgb_search.fit(X_train, y_train)
        xgb_val_acc = accuracy_score(y_val, xgb_search.predict(X_val))
        print(f"  Best XGB params: {xgb_search.best_params_}")
        print(f"  XGB CV score: {xgb_search.best_score_:.4f} | Val score: {xgb_val_acc:.4f}")
        tuned_models["XGBoost (tuned)"] = (xgb_search.best_estimator_, xgb_val_acc)
    except ImportError:
        pass

    # Pick the best tuned model
    best_name = max(tuned_models, key=lambda k: tuned_models[k][1])
    best_model, best_val_acc = tuned_models[best_name]
    print(f"\n  Champion: {best_name} (val={best_val_acc:.4f})")

    # ==================================================================
    # 5. FINAL EVALUATION on held-out test set
    #    This is the ONLY time we touch the test set.
    #    This number is the honest, unbiased estimate of real performance.
    # ==================================================================
    print("\n" + "=" * 58)
    print("  STAGE 3: FINAL EVALUATION (held-out test set)")
    print("=" * 58)

    y_pred = best_model.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)
    train_acc = accuracy_score(y_train, best_model.predict(X_train))
    target_names = [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)]

    print(f"\n  Train accuracy: {train_acc:.4f}")
    print(f"  Val accuracy:   {best_val_acc:.4f}")
    print(f"  Test accuracy:  {test_acc:.4f}")
    print(f"  Train→Test gap: {train_acc - test_acc:.4f}")
    print()

    print("Classification Report (TEST SET):")
    print(classification_report(y_test, y_pred, target_names=target_names))

    cm = confusion_matrix(y_test, y_pred)
    print("Confusion Matrix (TEST SET):")
    print(f"{'':>12}", end="")
    for n in target_names:
        print(f"{n:>12}", end="")
    print()
    for i, row in enumerate(cm):
        print(f"{target_names[i]:>12}", end="")
        for v in row:
            print(f"{v:>12}", end="")
        print()

    # Show where confusion happens
    print("\nKey confusion pairs:")
    for i in range(4):
        for j in range(4):
            if i != j and cm[i][j] > 2:
                print(f"  {target_names[i]} → {target_names[j]}: {cm[i][j]} samples")

    # Feature importances
    if hasattr(best_model, "feature_importances_"):
        print("\nFeature Importances:")
        for idx in np.argsort(best_model.feature_importances_)[::-1]:
            bar = "#" * int(best_model.feature_importances_[idx] * 40)
            print(f"  {X.columns[idx]:>25}: {best_model.feature_importances_[idx]:.3f} {bar}")

    # ==================================================================
    # 6. SAVE MODEL
    # ==================================================================
    save_path = os.path.join(current_dir, "model.joblib")
    joblib.dump(best_model, save_path)
    print(f"\nModel saved to: {save_path} ({os.path.getsize(save_path)/1024:.0f} KB)")

    # ==================================================================
    # 7. SANITY CHECK — reload and verify
    # ==================================================================
    print("\nSanity check (reload + predict 5 test samples):")
    reloaded = joblib.load(save_path)
    for i in range(min(5, len(X_test))):
        row = X_test.iloc[i:i+1]
        pred = reloaded.predict(row)[0]
        proba = reloaded.predict_proba(row)[0]
        actual = y_test.iloc[i]
        conf = max(proba)
        match = "OK" if pred == actual else "MISS"
        print(f"  [{match:>4}] predicted={CLASS_NAMES[pred]:>10} actual={CLASS_NAMES[actual]:>10} conf={conf:.3f}")


if __name__ == "__main__":
    train_and_compare()