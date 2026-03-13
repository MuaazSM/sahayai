"""
SahayAI Wearable Classifier — Prediction Module
=================================================
Loads the trained Random Forest model, classifies raw wearable data into
Normal / Fall / Wandering / Distress.

Called by the Perception Agent on every /check-status request.
Model loaded once on startup via load_classifier(); <5ms per prediction.
Falls back to hand-tuned rules if no model.joblib exists.

IMPORTANT: The 9th feature (gps_drift_rate) is computed as the average
distance from home in meters, NOT per-second GPS movement rate. This
matches how generate_wearable_data.py extracts the training features.
"""

import os
import math
import logging
import joblib
import numpy as np

logger = logging.getLogger("sahayai.classifier")

# Global model — loaded once on startup, reused for every prediction
_model = None
_model_loaded = False

# Class label mapping — matches the integer labels in the training data
CLASS_MAP = {0: "normal", 1: "fall", 2: "wandering", 3: "distress"}


def load_classifier():
    """
    Called once on server startup from main.py lifespan handler.
    Loads the trained model into memory so predictions are instant.
    If no model.joblib exists (Vaishnavi hasn't run train.py yet),
    we fall back to rule-based classification.
    """
    global _model, _model_loaded
    model_path = os.path.join(os.path.dirname(__file__), "model.joblib")

    if os.path.exists(model_path):
        _model = joblib.load(model_path)
        _model_loaded = True
        logger.info(f"Classifier loaded from {model_path}")
    else:
        _model_loaded = False
        logger.warning("No model.joblib found — using rule-based fallback classifier")


def classify_wearable(
    heart_rate: int,
    accel_x: float,
    accel_y: float,
    accel_z: float,
    steps: int,
    gps_lat: float,
    gps_lng: float,
    home_lat: float = 19.1136,
    home_lng: float = 72.8697,
    window_seconds: int = 30,
) -> dict:
    """
    Classify a single wearable reading snapshot.

    The /check-status endpoint sends a single-point reading, so we
    approximate what a 30-second window's extracted features would
    look like. This is inherently less accurate than having the full
    time series, but the rule-based fallback handles the critical
    cases (fall spikes, extreme HR) where single-point data is enough.

    Returns: {"classification": str, "confidence": float}
    """
    # --- Compute raw values from the single reading ---
    accel_mag = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
    dist_from_home_m = _haversine_meters(gps_lat, gps_lng, home_lat, home_lng)
    steps_per_sec = steps / max(window_seconds, 1)

    if _model_loaded and _model is not None:
        # ---------------------------------------------------------------
        # ML PATH: Build a 9-feature vector matching the training data.
        #
        # From a single snapshot we have to ESTIMATE what the window-level
        # features would be. These estimates are rough but sufficient
        # because the model's decision boundaries are robust.
        #
        # Feature order (must match training CSV columns):
        #   0: accel_magnitude_mean
        #   1: accel_magnitude_std
        #   2: accel_magnitude_max
        #   3: hr_mean
        #   4: hr_std
        #   5: hr_delta
        #   6: step_count
        #   7: movement_continuity
        #   8: gps_drift_rate (= avg distance from home in meters)
        # ---------------------------------------------------------------

        # Estimate accel_std and accel_max from the single reading:
        # A fall spike (high accel_mag) implies high std and max.
        # Walking (steps > 0) implies moderate std from rhythmic motion.
        # Sitting (low accel_mag near 9.8) implies very low std.
        if accel_mag > 15:
            # Looks like a fall spike — the window would have had
            # 3s normal (~9.8) + spike + 26s stillness (~5.0)
            est_mean = 7.0 + (accel_mag - 15) * 0.1
            est_std = accel_mag * 0.25
            est_max = accel_mag * 1.05
        elif steps_per_sec > 0.5:
            # Walking — rhythmic movement creates moderate std
            est_mean = accel_mag
            est_std = 0.3 + steps_per_sec * 0.1
            est_max = accel_mag * 1.15
        else:
            # Sedentary — very low variation
            est_mean = accel_mag
            est_std = 0.1 + abs(accel_mag - 9.8) * 0.1
            est_max = accel_mag * 1.05

        # Estimate HR delta from single reading:
        # If HR is very high, assume it jumped from baseline → positive delta
        # If HR is normal, assume stable → near-zero delta
        if heart_rate > 110:
            est_hr_delta = (heart_rate - 75) * 0.6
        elif heart_rate > 95:
            est_hr_delta = (heart_rate - 75) * 0.3
        else:
            est_hr_delta = 0.0

        # HR std: approximate from how far HR is from resting range
        if heart_rate > 100:
            est_hr_std = 5.0 + (heart_rate - 100) * 0.15
        else:
            est_hr_std = 2.5

        features = np.array([[
            est_mean,                       # accel_magnitude_mean
            est_std,                        # accel_magnitude_std
            est_max,                        # accel_magnitude_max
            float(heart_rate),              # hr_mean
            est_hr_std,                     # hr_std
            est_hr_delta,                   # hr_delta
            steps,                          # step_count
            steps_per_sec,                  # movement_continuity
            dist_from_home_m,               # gps_drift_rate (= avg dist from home)
        ]])

        prediction = _model.predict(features)[0]
        proba = _model.predict_proba(features)[0]
        confidence = float(max(proba))
        classification = CLASS_MAP.get(prediction, "normal")

        logger.info(f"ML: {classification} (conf={confidence:.2f}, dist_home={dist_from_home_m:.0f}m)")
        return {"classification": classification, "confidence": confidence}

    else:
        # ---------------------------------------------------------------
        # RULE-BASED FALLBACK
        # Hand-tuned thresholds that match the training data distributions.
        # These handle the most critical cases (falls, wandering far from
        # home, extreme HR) where missing a detection could be dangerous.
        # ---------------------------------------------------------------
        return _rule_based_classify(
            accel_mag, heart_rate, steps, steps_per_sec, dist_from_home_m
        )


def _rule_based_classify(accel_mag, hr, steps, steps_per_sec, dist_m) -> dict:
    """
    Rule-based fallback — ensures /check-status works even without
    model.joblib. Tuned to match the class boundaries from training data.
    """
    # FALL: sudden high acceleration spike + elevated heart rate
    # Training data: falls have accel_max > 10 (moderate) to 42 (hard)
    # and hr_mean 76-109 with hr_delta > 3.6
    if accel_mag > 25.0 and hr > 90:
        return {"classification": "fall", "confidence": 0.85}
    if accel_mag > 35.0:
        return {"classification": "fall", "confidence": 0.75}

    # WANDERING: far from home + walking
    # Training data: wandering has gps_drift_rate 32-803m
    if dist_m > 200 and steps_per_sec > 0.5:
        return {"classification": "wandering", "confidence": 0.85}
    if dist_m > 500:
        return {"classification": "wandering", "confidence": 0.75}
    if dist_m > 100 and steps_per_sec > 1.0:
        return {"classification": "wandering", "confidence": 0.70}

    # DISTRESS: very high HR without purposeful locomotion
    # Training data: distress has hr_mean 86-145
    if hr > 120 and steps_per_sec < 0.3:
        return {"classification": "distress", "confidence": 0.80}
    if hr > 140:
        return {"classification": "distress", "confidence": 0.75}
    if hr > 105 and steps_per_sec < 0.2:
        return {"classification": "distress", "confidence": 0.65}

    # NORMAL: everything within expected ranges
    return {"classification": "normal", "confidence": 0.90}


def _haversine_meters(lat1, lng1, lat2, lng2) -> float:
    """
    Distance between two GPS points in meters.
    Used to compute how far the person is from home.
    """
    R = 6_371_000  # earth radius in meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))