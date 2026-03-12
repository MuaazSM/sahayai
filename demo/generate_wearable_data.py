import pandas as pd
import numpy as np
import os

def generate_samples(num_samples=2500):
    data = []
    
    for _ in range(num_samples):
        # NORMAL
        data.append({"accel_mean": np.random.uniform(0.9, 1.1), "accel_std": np.random.uniform(0.05, 0.3), "accel_max": np.random.uniform(1.0, 1.5), "hr_mean": np.random.uniform(67, 77), "hr_std": np.random.uniform(1, 3), "hr_delta": np.random.uniform(-2, 2), "step_count": np.random.randint(0, 10), "movement_continuity": np.random.uniform(0.0, 0.2), "gps_drift_rate": 0.0, "label": "normal"})
        # FALL
        data.append({"accel_mean": np.random.uniform(1.5, 3.0), "accel_std": np.random.uniform(3.0, 6.0), "accel_max": np.random.uniform(15.0, 25.0), "hr_mean": np.random.uniform(85, 110), "hr_std": np.random.uniform(5, 15), "hr_delta": np.random.uniform(20, 35), "step_count": np.random.randint(0, 5), "movement_continuity": np.random.uniform(0.0, 0.1), "gps_drift_rate": 0.0, "label": "fall"})
        # WANDERING
        data.append({"accel_mean": np.random.uniform(1.2, 2.0), "accel_std": np.random.uniform(0.5, 1.5), "accel_max": np.random.uniform(2.0, 4.0), "hr_mean": np.random.uniform(80, 95), "hr_std": np.random.uniform(2, 6), "hr_delta": np.random.uniform(5, 15), "step_count": np.random.randint(30, 60), "movement_continuity": np.random.uniform(0.8, 1.0), "gps_drift_rate": np.random.uniform(1.0, 1.5), "label": "wandering"})
        # DISTRESS
        data.append({"accel_mean": np.random.uniform(2.0, 4.0), "accel_std": np.random.uniform(2.0, 5.0), "accel_max": np.random.uniform(5.0, 10.0), "hr_mean": np.random.uniform(100, 130), "hr_std": np.random.uniform(10, 25), "hr_delta": np.random.uniform(15, 45), "step_count": np.random.randint(5, 20), "movement_continuity": np.random.uniform(0.3, 0.7), "gps_drift_rate": np.random.uniform(0.0, 0.5), "label": "distress"})
        
    return pd.DataFrame(data)

if __name__ == "__main__":
    print("Generating 10,000 synthetic smartwatch events...")
    df = generate_samples(2500)
    
    # Save to the data folder
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)
    
    csv_path = os.path.join(data_dir, "wearable_features.csv")
    df.to_csv(csv_path, index=False)
    print(f"✅ Successfully saved {len(df)} samples to {csv_path}!")