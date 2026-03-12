import pandas as pd
import numpy as np
import os

def generate_samples(num_samples=2500):
    data = []
    
    for _ in range(num_samples):
        # 0. NORMAL: General daily activity (The "Baseline")
        data.append({
            "accel_mean": np.random.normal(1.02, 0.15), 
            "accel_std": np.random.normal(0.12, 0.05), 
            "accel_max": np.random.normal(1.4, 0.2), 
            "hr_mean": np.random.normal(74, 6), 
            "hr_std": np.random.uniform(1, 4), 
            "hr_delta": np.random.normal(0, 2), 
            "step_count": np.random.randint(0, 20), 
            "movement_continuity": np.random.uniform(0.1, 0.4), 
            "gps_drift_rate": 0.0, 
            "label": 0
        })
        
        # 1. FALL: High impact spike followed by low movement
        data.append({
            "accel_mean": np.random.normal(1.8, 0.5), 
            "accel_std": np.random.normal(3.5, 1.2), 
            "accel_max": np.random.normal(14.0, 4.0), 
            "hr_mean": np.random.normal(98, 12), 
            "hr_std": np.random.uniform(6, 15), 
            "hr_delta": np.random.normal(22, 8), 
            "step_count": np.random.randint(0, 8), 
            "movement_continuity": np.random.uniform(0.0, 0.15), 
            "gps_drift_rate": 0.0, 
            "label": 1
        })
        
        # 2. WANDERING: High continuous movement + distance from home
        data.append({
            "accel_mean": np.random.normal(1.4, 0.3), 
            "accel_std": np.random.normal(0.7, 0.2), 
            "accel_max": np.random.normal(3.2, 0.8), 
            "hr_mean": np.random.normal(90, 8), 
            "hr_std": np.random.uniform(3, 8), 
            "hr_delta": np.random.normal(8, 5), 
            "step_count": np.random.randint(35, 75), 
            "movement_continuity": np.random.uniform(0.75, 1.0), 
            "gps_drift_rate": np.random.normal(1.2, 0.4), 
            "label": 2
        })
        
        # 3. DISTRESS: High HR without high movement (Panic Attack)
        data.append({
            "accel_mean": np.random.normal(1.1, 0.2), 
            "accel_std": np.random.normal(0.8, 0.4), 
            "accel_max": np.random.normal(2.5, 1.0), 
            "hr_mean": np.random.normal(115, 15), 
            "hr_std": np.random.normal(12, 5), 
            "hr_delta": np.random.normal(25, 10), 
            "step_count": np.random.randint(0, 12), 
            "movement_continuity": np.random.uniform(0.2, 0.6), 
            "gps_drift_rate": np.random.uniform(0.0, 0.4), 
            "label": 3
        })
        
    return pd.DataFrame(data)

if __name__ == "__main__":
    print("🚀 SahayAI: Generating 10,000 REALISTIC smartwatch events...")
    df = generate_samples(2500)
    
    # Ensures it goes to backend/data regardless of where you run it from
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, "backend", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    csv_path = os.path.join(data_dir, "wearable_features.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"✅ Saved realistic dataset to: {csv_path}")