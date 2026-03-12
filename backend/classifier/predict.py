import os
import math
import logging
import joblib
import numpy as np

logger = logging.getLogger("sahayai.classifier")

# We load the trained model into this global variable once on startup
# so we don't re-read the file on every /check-status call
_model = None
_model_loaded = False


def load_classifier():
    """Called once on server startup from main.py lifespan handler"""
    global _model, _model_loaded
    model_path = os.path.join(os.path.dirname(__file__), "model.joblib")

    if os.path.exists(model_path):
        _model = joblib.load(model_path)
        _model_loaded = True
        logger.info(f"Classifier loaded from {model_path}")
    else:
        # No trained model yet — Vaishnavi hasn't run train.py
        # We'll fall back to rule-based classification
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
    Takes raw wearable sensor data and returns a classification.
    If trained model exists, uses Random Forest. Otherwise uses
    hand-written rules that approximate the same logic — good enough
    for the demo until Vaishnavi's model is ready.

    Returns: {"classification": str, "confidence": float}
    """

    # --- Feature extraction ---
    # These are the same features the trained model expects
    accel_magnitude = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)

    # Distance from home in meters (rough haversine approximation)
    # Good enough for Mumbai-scale distances
    dist_from_home = _haversine_meters(gps_lat, gps_lng, home_lat, home_lng)

    # Steps per second — tells us if they're walking continuously
    steps_per_sec = steps / max(window_seconds, 1)

    if _model_loaded and _model is not None:
        # --- ML path: use the trained Random Forest ---
        features = np.array([[
            accel_magnitude,
            heart_rate,
            steps,
            steps_per_sec,
            dist_from_home,
        ]])

        prediction = _model.predict(features)[0]
        probabilities = _model.predict_proba(features)[0]
        confidence = float(max(probabilities))

        # The model outputs class labels: 0=normal, 1=fall, 2=wandering, 3=distress
        class_map = {0: "normal", 1: "fall", 2: "wandering", 3: "distress"}
        classification = class_map.get(prediction, "normal")

        logger.info(f"ML classifier: {classification} (confidence={confidence:.2f})")
        return {"classification": classification, "confidence": confidence}

    else:
        # --- Rule-based fallback ---
        # These thresholds are based on the synthetic data distribution
        # Vaishnavi used to train the model. Not perfect but gets the
        # demo scenarios right.
        return _rule_based_classify(
            accel_magnitude, heart_rate, steps, steps_per_sec, dist_from_home
        )


def _rule_based_classify(accel_mag, hr, steps, steps_per_sec, dist_from_home) -> dict:
    """
    Hand-tuned rules that match the 4 classes in our training data.
    This is the safety net so /check-status works even without model.joblib
    """

    # FALL: sudden high acceleration spike + elevated heart rate
    # A fall produces a huge accel spike (>25 m/s²) followed by near-zero movement
    if accel_mag > 25.0 and hr > 90:
        return {"classification": "fall", "confidence": 0.85}

    # FALL: extreme acceleration even without HR spike
    if accel_mag > 35.0:
        return {"classification": "fall", "confidence": 0.75}

    # WANDERING: far from home + continuous walking
    # Ramesh's geofence is ~500m. If he's beyond that and actively walking,
    # he's probably wandering (especially with low AAC score)
    if dist_from_home > 500 and steps_per_sec > 0.5:
        return {"classification": "wandering", "confidence": 0.80}

    # WANDERING: very far from home regardless of movement
    if dist_from_home > 1000:
        return {"classification": "wandering", "confidence": 0.70}

    # DISTRESS: abnormal heart rate (too high or too low) + low movement
    # Could indicate a panic attack, pain, or medical event
    if (hr > 120 or hr < 45) and steps_per_sec < 0.3:
        return {"classification": "distress", "confidence": 0.75}

    # DISTRESS: very high heart rate regardless
    if hr > 140:
        return {"classification": "distress", "confidence": 0.70}

    # NORMAL: everything looks fine
    return {"classification": "normal", "confidence": 0.90}


def _haversine_meters(lat1, lng1, lat2, lng2) -> float:
    """
    Quick and dirty distance between two GPS points in meters.
    Not perfectly accurate but close enough for "is Ramesh near home?"
    """
    R = 6371000  # earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c