"""
Test the 4 innovation modules independently:
CCT, AAC, EMR retrieval logic, CBD
"""

import pytest
from datetime import datetime


class TestClassifierFeatures:
    """Test the feature extraction and classification edge cases"""

    def test_normal_at_home(self):
        from classifier.predict import classify_wearable
        r = classify_wearable(72, 0.1, 0.2, 9.8, 5, 19.1136, 72.8697)
        assert r["classification"] == "normal"

    def test_borderline_fall_low_confidence(self):
        """High accel spike + elevated HR = fall even at lower magnitude"""
        from classifier.predict import classify_wearable
        r = classify_wearable(95, 12.0, 15.0, 18.0, 0, 19.1136, 72.8697)
        assert r["classification"] == "fall"

    def test_walking_near_home_is_normal(self):
        """Walking nearby with normal HR = just a normal walk"""
        from classifier.predict import classify_wearable
        r = classify_wearable(80, 1.0, 0.8, 9.9, 30, 19.1137, 72.8698)
        assert r["classification"] == "normal"


class TestAACSundowning:
    """Verify the time-of-day component follows the sundowning curve"""

    def test_morning_scores_highest(self):
        from innovations.aac import _compute_time_component
        from unittest.mock import patch
        from datetime import datetime as dt

        # Mock 8 AM — morning should score ~85
        with patch("innovations.aac.datetime") as mock_dt:
            mock_dt.utcnow.return_value = dt(2026, 3, 13, 8, 0, 0)
            score = _compute_time_component()
            assert score >= 80

    def test_evening_scores_lowest(self):
        from innovations.aac import _compute_time_component
        from unittest.mock import patch
        from datetime import datetime as dt

        # Mock 6 PM — evening sundowning should score ~50
        with patch("innovations.aac.datetime") as mock_dt:
            mock_dt.utcnow.return_value = dt(2026, 3, 13, 18, 0, 0)
            score = _compute_time_component()
            assert score <= 55

    def test_night_scores_very_low(self):
        from innovations.aac import _compute_time_component
        from unittest.mock import patch
        from datetime import datetime as dt

        # Mock 2 AM — night disorientation risk high
        with patch("innovations.aac.datetime") as mock_dt:
            mock_dt.utcnow.return_value = dt(2026, 3, 13, 2, 0, 0)
            score = _compute_time_component()
            assert score <= 50


class TestCBDInterventions:
    """Verify graduated CBD intervention thresholds"""

    def test_no_intervention_low_score(self):
        from innovations.cbd import _get_intervention
        assert _get_intervention(15.0) is None

    def test_gentle_reminder_moderate_score(self):
        from innovations.cbd import _get_intervention
        msg = _get_intervention(35.0)
        assert msg is not None
        assert "care of yourself" in msg.lower() or "you matter" in msg.lower()

    def test_suggest_respite_high_score(self):
        from innovations.cbd import _get_intervention
        msg = _get_intervention(55.0)
        assert msg is not None
        assert "break" in msg.lower() or "recharge" in msg.lower()

    def test_increase_autonomy_very_high(self):
        from innovations.cbd import _get_intervention
        msg = _get_intervention(75.0)
        assert msg is not None
        assert "someone" in msg.lower() or "cover" in msg.lower()

    def test_alert_secondary_critical(self):
        from innovations.cbd import _get_intervention
        msg = _get_intervention(90.0)
        assert msg is not None
        assert "family member" in msg.lower() or "notify" in msg.lower()

    def test_intervention_levels_correct(self):
        from innovations.cbd import _get_intervention_level
        assert _get_intervention_level(10) == "none"
        assert _get_intervention_level(35) == "gentle"
        assert _get_intervention_level(55) == "suggest_respite"
        assert _get_intervention_level(75) == "increase_autonomy"
        assert _get_intervention_level(90) == "alert_secondary"