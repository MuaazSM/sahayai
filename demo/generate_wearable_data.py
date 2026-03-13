"""
SahayAI Smartwatch Simulator v5 — Thick Boundary Overlap
==========================================================
v4 problem: single features could perfectly separate classes because
boundary variants were too rare (15% of samples). A depth-1 decision
tree on step_count alone got 100% on Falls.

v5 fixes:
  - 35% of Normal = outdoor walks/exercise (GPS 50-500m, steps 20-80, HR 85-110)
  - 40% of Falls = stumbles/near-falls (accel_max 4-12, overlaps normal chair-stands)
  - 35% of Wandering = early/slow (GPS 30-200m, steps 12-40, overlaps normal walks)
  - 40% of Distress = mild anxiety (HR 80-100, overlaps normal exercise)

Design principle: for EVERY feature, at least 25% of two different classes
should share the same value range. No single feature should achieve >80%
per-class accuracy with a single threshold.

Target: 92-96% RF accuracy. Logistic Regression ~85-90%.

Run:  python demo/generate_wearable_data.py
"""

import numpy as np
import pandas as pd
import os

np.random.seed(42)

WINDOW_SEC = 30
SAMPLES_PER_CLASS = 2500
HOME_LAT = 19.1136
HOME_LNG = 72.8697
DEG_PER_METER = 1.0 / 111_000.0
GPS_NOISE_STD = 4.0  # same for ALL classes


# =====================================================
# NORMAL — 4 sub-variants with thick overlap into other classes
# =====================================================

def _gen_normal():
    """
    Sub-variants (weighted to create thick overlap):
      30% — Sitting/resting (classic baseline)
      15% — Housework with exertion (HR overlaps distress, accel overlaps distress)
      20% — Outdoor walk near home (steps + GPS overlaps early wandering)
      15% — Brisk exercise (high HR + high steps, overlaps wandering + distress)
      10% — Chair stand / reaching (accel spike overlaps mild falls)
      10% — Anxious but fine (elevated HR + fidgeting, overlaps mild distress)
    """
    variant = np.random.choice(
        ["sitting", "housework", "outdoor_walk", "exercise", "chair_stand", "anxious"],
        p=[0.30, 0.15, 0.20, 0.15, 0.10, 0.10]
    )
    t = np.arange(WINDOW_SEC)

    if variant == "sitting":
        ax = np.random.normal(0, 0.12, WINDOW_SEC)
        ay = np.random.normal(0, 0.12, WINDOW_SEC)
        az = np.random.normal(9.8, 0.08, WINDOW_SEC)
        base_hr = np.random.uniform(58, 82)
        hr = base_hr + np.random.normal(0, 1.5, WINDOW_SEC)
        steps = np.zeros(WINDOW_SEC, dtype=int)
        n = np.random.randint(0, 4)
        if n > 0:
            steps[np.random.choice(WINDOW_SEC, n, replace=False)] = 1
        gps_offset_m = np.random.uniform(0, 15)

    elif variant == "housework":
        # Moderate arm movement + occasional spikes from bending/lifting
        ax = np.random.normal(0, 0.7, WINDOW_SEC)
        ay = np.random.normal(0, 0.5, WINDOW_SEC)
        az = np.random.normal(9.8, 0.3, WINDOW_SEC)
        for _ in range(np.random.randint(3, 8)):
            i = np.random.randint(0, WINDOW_SEC)
            ax[i] += np.random.uniform(2, 6) * np.random.choice([-1, 1])
            ay[i] += np.random.uniform(1.5, 4) * np.random.choice([-1, 1])
        # HR elevated from physical work — overlaps with mild distress range
        base_hr = np.random.uniform(78, 100)
        hr = base_hr + np.random.normal(0, 4, WINDOW_SEC)
        # Some walking mixed in
        steps = np.zeros(WINDOW_SEC, dtype=int)
        walk_dur = np.random.randint(5, 15)
        walk_start = np.random.randint(0, WINDOW_SEC - walk_dur)
        steps[walk_start:walk_start + walk_dur] = np.random.randint(1, 3, walk_dur)
        gps_offset_m = np.random.uniform(0, 30)

    elif variant == "outdoor_walk":
        # Walking to park, shop, neighbor — GPS goes 50-500m from home
        # Step pattern, HR, and movement OVERLAPS with early wandering
        freq = np.random.uniform(1.5, 2.1)
        amp = np.random.uniform(0.8, 2.0)
        ax = amp * np.sin(2 * np.pi * freq * t) + np.random.normal(0, 0.3, WINDOW_SEC)
        ay = (amp * 0.5) * np.cos(2 * np.pi * freq * t) + np.random.normal(0, 0.2, WINDOW_SEC)
        az = 9.8 + (amp * 0.35) * np.sin(4 * np.pi * freq * t) + np.random.normal(0, 0.15, WINDOW_SEC)
        base_hr = np.random.uniform(78, 98)
        hr = base_hr + np.random.normal(0, 3, WINDOW_SEC)
        step_rate = np.random.uniform(1.5, 3.2)
        steps = np.array([max(0, int(np.random.poisson(step_rate))) for _ in range(WINDOW_SEC)])
        # KEY: GPS 50-500m from home — overlaps with early wandering (30-200m)
        gps_offset_m = np.random.uniform(50, 500)

    elif variant == "exercise":
        # Intentional exercise: high HR + high steps + high accel
        # Overlaps wandering (high steps) AND distress (high HR)
        freq = np.random.uniform(1.8, 2.5)
        amp = np.random.uniform(1.5, 3.0)
        ax = amp * np.sin(2 * np.pi * freq * t) + np.random.normal(0, 0.4, WINDOW_SEC)
        ay = (amp * 0.6) * np.cos(2 * np.pi * freq * t) + np.random.normal(0, 0.3, WINDOW_SEC)
        az = 9.8 + (amp * 0.5) * np.sin(4 * np.pi * freq * t) + np.random.normal(0, 0.2, WINDOW_SEC)
        # High HR from exercise — overlaps with distress HR range
        base_hr = np.random.uniform(90, 115)
        hr = base_hr + np.random.normal(0, 4, WINDOW_SEC)
        step_rate = np.random.uniform(2.5, 4.0)
        steps = np.array([max(0, int(np.random.poisson(step_rate))) for _ in range(WINDOW_SEC)])
        # Exercise near home or at park
        gps_offset_m = np.random.uniform(20, 400)

    elif variant == "chair_stand":
        # Getting up produces accel spike — overlaps mild fall accel_max range
        ax = np.random.normal(0, 0.15, WINDOW_SEC)
        ay = np.random.normal(0, 0.15, WINDOW_SEC)
        az = np.random.normal(9.8, 0.1, WINDOW_SEC)
        stand_t = np.random.randint(5, 20)
        stand_dur = np.random.randint(1, 3)
        for i in range(stand_t, min(stand_t + stand_dur, WINDOW_SEC)):
            # Spike magnitude 3-10g — overlaps with stumble falls (4-12g)
            ax[i] = np.random.uniform(3, 10) * np.random.choice([-1, 1])
            ay[i] = np.random.uniform(2, 7) * np.random.choice([-1, 1])
            az[i] = np.random.uniform(6, 13)
        for i in range(stand_t + stand_dur, min(stand_t + stand_dur + 3, WINDOW_SEC)):
            ax[i] = np.random.normal(0, 0.5)
            ay[i] = np.random.normal(0, 0.5)
        base_hr = np.random.uniform(68, 88)
        hr = np.full(WINDOW_SEC, base_hr, dtype=float) + np.random.normal(0, 2, WINDOW_SEC)
        hr[stand_t:min(stand_t + 6, WINDOW_SEC)] += np.random.uniform(5, 18)
        steps = np.zeros(WINDOW_SEC, dtype=int)
        post = min(stand_t + stand_dur + 1, WINDOW_SEC)
        n_post = np.random.randint(0, 6)
        if n_post > 0 and post < WINDOW_SEC:
            idx = np.random.choice(range(post, WINDOW_SEC), min(n_post, WINDOW_SEC - post), replace=False)
            steps[idx] = 1
        gps_offset_m = np.random.uniform(0, 15)

    else:  # anxious
        # Elevated HR + fidgeting but nothing is actually wrong
        # Overlaps mild distress almost completely on HR + accel
        ax = np.random.normal(0, 0.5, WINDOW_SEC)
        ay = np.random.normal(0, 0.4, WINDOW_SEC)
        az = np.random.normal(9.8, 0.2, WINDOW_SEC)
        # Fidget spikes
        for _ in range(np.random.randint(2, 6)):
            i = np.random.randint(0, WINDOW_SEC)
            ax[i] += np.random.uniform(1, 4) * np.random.choice([-1, 1])
        # HR in the mild-distress range
        base_hr = np.random.uniform(85, 105)
        hr = base_hr + np.random.normal(0, 5, WINDOW_SEC)
        # A few restless steps
        steps = np.zeros(WINDOW_SEC, dtype=int)
        n = np.random.randint(2, 10)
        steps[np.random.choice(WINDOW_SEC, n, replace=False)] = 1
        gps_offset_m = np.random.uniform(0, 30)

    hr = np.clip(hr, 50, 120)

    # GPS: offset from home based on variant
    angle = np.random.uniform(0, 2 * np.pi)
    lat = HOME_LAT + gps_offset_m * np.cos(angle) * DEG_PER_METER + np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)
    lng = HOME_LNG + gps_offset_m * np.sin(angle) * DEG_PER_METER + np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)

    return {"ax": ax, "ay": ay, "az": az, "hr": hr, "steps": steps, "lat": lat, "lng": lng}


# =====================================================
# FALL — more stumbles and slow falls to thicken the boundary
# =====================================================

def _gen_fall():
    """
    Sub-variants:
      25% — Hard fall: spike 18-35g, HR +25-40, stillness
      20% — Moderate fall: spike 10-18g, HR +15-25, some shifting
      30% — Stumble/trip: spike 4-12g, HR +5-18, may resume moving
            (Thick overlap with normal chair_stand on accel, HR)
      15% — Slow fall/slide: gradual 3-8g, HR +8-18
      10% — Fall during walk: was walking (has steps!), then falls
            (Overlaps wandering on step_count in first half of window)
    """
    severity = np.random.choice(
        ["hard", "moderate", "stumble", "slow", "walk_fall"],
        p=[0.25, 0.20, 0.30, 0.15, 0.10]
    )
    t = np.arange(WINDOW_SEC)

    ax = np.random.normal(0, 0.2, WINDOW_SEC)
    ay = np.random.normal(0, 0.2, WINDOW_SEC)
    az = np.random.normal(9.8, 0.15, WINDOW_SEC)

    # Pre-fall walking for walk_fall variant
    if severity == "walk_fall":
        pre_dur = np.random.randint(8, 18)
        freq = np.random.uniform(1.5, 2.0)
        amp = np.random.uniform(0.8, 1.5)
        for i in range(pre_dur):
            ax[i] = amp * np.sin(2 * np.pi * freq * i) + np.random.normal(0, 0.2)
            ay[i] = amp * 0.5 * np.cos(2 * np.pi * freq * i) + np.random.normal(0, 0.15)
            az[i] = 9.8 + amp * 0.3 * np.sin(4 * np.pi * freq * i)
    else:
        pre_dur = np.random.randint(2, 6)

    impact_t = pre_dur
    impact_dur = np.random.choice([1, 2])

    if severity == "hard":
        spike_min, spike_max = 18, 35
        hr_jump = np.random.uniform(25, 40)
        post_noise = 0.03
        post_az = np.random.uniform(3.0, 7.0)
    elif severity == "moderate":
        spike_min, spike_max = 10, 18
        hr_jump = np.random.uniform(15, 25)
        post_noise = 0.12
        post_az = np.random.uniform(5.0, 8.5)
    elif severity == "stumble":
        # Spike 4-12g overlaps with normal chair_stand (3-10g)
        spike_min, spike_max = 4, 12
        hr_jump = np.random.uniform(5, 18)
        post_noise = 0.35
        post_az = np.random.uniform(8.0, 10.0)  # stays mostly upright
    elif severity == "slow":
        spike_min, spike_max = 3, 8
        hr_jump = np.random.uniform(8, 18)
        post_noise = 0.15
        post_az = np.random.uniform(5.0, 9.0)
    else:  # walk_fall
        spike_min, spike_max = 10, 25
        hr_jump = np.random.uniform(15, 30)
        post_noise = 0.05
        post_az = np.random.uniform(3.5, 7.0)

    # Impact
    for i in range(impact_t, min(impact_t + impact_dur, WINDOW_SEC)):
        ax[i] = np.random.uniform(spike_min, spike_max) * np.random.choice([-1, 1])
        ay[i] = np.random.uniform(spike_min * 0.4, spike_max * 0.7) * np.random.choice([-1, 1])
        az[i] = np.random.uniform(2, spike_max * 0.8)

    # Slow fall: gradual buildup
    if severity == "slow":
        buildup_start = max(0, impact_t - 4)
        for i in range(buildup_start, impact_t):
            progress = (i - buildup_start) / max(1, impact_t - buildup_start)
            ax[i] = np.random.uniform(1, 4) * progress * np.random.choice([-1, 1])
            ay[i] = np.random.uniform(0.5, 3) * progress * np.random.choice([-1, 1])

    # Post-fall
    for i in range(min(impact_t + impact_dur, WINDOW_SEC), WINDOW_SEC):
        ax[i] = np.random.normal(0, post_noise)
        ay[i] = np.random.normal(0, post_noise)
        az[i] = np.random.normal(post_az, post_noise + 0.1)

    # HR
    base_hr = np.random.uniform(65, 85)
    hr = np.full(WINDOW_SEC, base_hr, dtype=float) + np.random.normal(0, 2, WINDOW_SEC)
    hr[impact_t:] += hr_jump + np.random.normal(0, 4, WINDOW_SEC - impact_t)
    if severity == "stumble":
        recovery = min(impact_t + impact_dur + np.random.randint(3, 8), WINDOW_SEC)
        if recovery < WINDOW_SEC:
            hr[recovery:] -= hr_jump * np.random.uniform(0.3, 0.6)
    hr = np.clip(hr, 55, 170)

    # Steps
    steps = np.zeros(WINDOW_SEC, dtype=int)
    if severity == "walk_fall":
        # Was walking before the fall — high step count in first half
        step_rate = np.random.uniform(1.5, 3.0)
        for i in range(pre_dur):
            steps[i] = max(0, int(np.random.poisson(step_rate)))
    else:
        n_pre = np.random.randint(0, min(3, pre_dur + 1))
        if n_pre > 0 and pre_dur > 0:
            steps[np.random.choice(pre_dur, n_pre, replace=False)] = 1
    if severity == "stumble":
        resume = min(impact_t + impact_dur + np.random.randint(2, 6), WINDOW_SEC)
        for i in range(resume, WINDOW_SEC):
            if np.random.random() < 0.5:
                steps[i] = 1

    # GPS: mostly at home, walk_fall might be outside
    if severity == "walk_fall":
        offset = np.random.uniform(30, 300)
    else:
        offset = np.random.uniform(0, 20)
    angle = np.random.uniform(0, 2 * np.pi)
    lat = HOME_LAT + offset * np.cos(angle) * DEG_PER_METER + np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)
    lng = HOME_LNG + offset * np.sin(angle) * DEG_PER_METER + np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)

    return {"ax": ax, "ay": ay, "az": az, "hr": hr, "steps": steps, "lat": lat, "lng": lng}


# =====================================================
# WANDERING — more early/slow variants to overlap with normal walks
# =====================================================

def _gen_wandering():
    """
    Sub-variants:
      30% — Full wandering: 300m+, continuous walk
      25% — Early wandering: 80-250m (overlaps normal outdoor_walk 50-500m)
      25% — Slow confused: 30-120m, intermittent, low steps
            (heavily overlaps normal outdoor_walk)
      20% — Confused pacing: 5-60m from home, erratic
            (overlaps normal housework/anxious on most features)
    """
    variant = np.random.choice(
        ["full", "early", "slow", "pacing"],
        p=[0.30, 0.25, 0.25, 0.20]
    )
    t = np.arange(WINDOW_SEC)

    if variant == "full":
        freq = np.random.uniform(1.8, 2.2)
        amp = np.random.uniform(1.5, 2.5)
        init_offset = np.random.uniform(300, 1000)
        drift_mps = np.random.uniform(0.8, 1.6)
        base_hr = np.random.uniform(82, 102)
        step_rate = np.random.uniform(2.0, 3.5)

    elif variant == "early":
        freq = np.random.uniform(1.5, 2.0)
        amp = np.random.uniform(0.8, 1.6)
        # GPS 80-250m — overlaps normal outdoor_walk (50-500m)
        init_offset = np.random.uniform(80, 250)
        drift_mps = np.random.uniform(0.4, 1.0)
        base_hr = np.random.uniform(78, 95)
        # Steps overlaps normal outdoor walk (1.5-3.2)
        step_rate = np.random.uniform(1.2, 2.5)

    elif variant == "slow":
        freq = np.random.uniform(1.0, 1.6)
        amp = np.random.uniform(0.5, 1.2)
        # GPS 30-120m — heavily overlaps normal outdoor_walk
        init_offset = np.random.uniform(30, 120)
        drift_mps = np.random.uniform(0.2, 0.7)
        base_hr = np.random.uniform(74, 90)
        step_rate = np.random.uniform(0.6, 1.8)

    else:  # pacing
        freq = np.random.uniform(0.8, 1.5)
        amp = np.random.uniform(0.4, 1.0)
        # Very close to home — overlaps normal on GPS
        init_offset = np.random.uniform(5, 60)
        drift_mps = np.random.uniform(0.1, 0.3)
        base_hr = np.random.uniform(78, 98)
        step_rate = np.random.uniform(0.5, 2.0)

    # Walking accel
    ax = amp * np.sin(2 * np.pi * freq * t) + np.random.normal(0, 0.3, WINDOW_SEC)
    ay = (amp * 0.6) * np.cos(2 * np.pi * freq * t) + np.random.normal(0, 0.2, WINDOW_SEC)
    az = 9.8 + (amp * 0.4) * np.sin(4 * np.pi * freq * t) + np.random.normal(0, 0.15, WINDOW_SEC)

    # Slow/pacing: add pauses and irregularity
    if variant in ("slow", "pacing"):
        n_pauses = np.random.randint(4, 10)
        for _ in range(n_pauses):
            p_start = np.random.randint(0, WINDOW_SEC - 3)
            p_dur = np.random.randint(1, 5)
            for j in range(p_start, min(p_start + p_dur, WINDOW_SEC)):
                ax[j] = np.random.normal(0, 0.2)
                ay[j] = np.random.normal(0, 0.2)
                az[j] = np.random.normal(9.8, 0.1)

    hr = base_hr + np.random.normal(0, 3, WINDOW_SEC)
    hr += np.linspace(0, np.random.uniform(0, 5), WINDOW_SEC)
    hr = np.clip(hr, 58, 125)

    steps = np.array([max(0, int(np.random.poisson(step_rate))) for _ in range(WINDOW_SEC)])
    if variant in ("slow", "pacing"):
        for _ in range(np.random.randint(4, 9)):
            s = np.random.randint(0, WINDOW_SEC - 2)
            d = np.random.randint(1, 5)
            steps[s:min(s+d, WINDOW_SEC)] = 0

    # GPS drift
    angle = np.random.uniform(0, 2 * np.pi)
    if variant == "pacing":
        angles = angle + np.cumsum(np.random.normal(0, 0.5, WINDOW_SEC))
        cum_dist = np.cumsum(np.abs(np.random.normal(drift_mps, 0.2, WINDOW_SEC)))
        lat = HOME_LAT + (init_offset + cum_dist * np.cos(angles)) * DEG_PER_METER
        lng = HOME_LNG + (init_offset + cum_dist * np.sin(angles)) * DEG_PER_METER
    else:
        lat = HOME_LAT + (init_offset + drift_mps * t) * np.cos(angle) * DEG_PER_METER
        lng = HOME_LNG + (init_offset + drift_mps * t) * np.sin(angle) * DEG_PER_METER
    lat += np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)
    lng += np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)

    return {"ax": ax, "ay": ay, "az": az, "hr": hr, "steps": steps, "lat": lat, "lng": lng}


# =====================================================
# DISTRESS — more mild variants to overlap with normal
# =====================================================

def _gen_distress():
    """
    Sub-variants:
      25% — Severe: HR 115-150, heavy tremor, near-zero steps
      25% — Moderate: HR 95-120, tremor, some shuffling
      30% — Mild anxiety: HR 80-105, slight tremor, a few steps
            (HR + accel overlaps normal housework/anxious/exercise)
      20% — Agitated pacing: HR 88-115, walk-like + tremor, moderate steps
            (Overlaps wandering pacing on steps + accel pattern)
    """
    variant = np.random.choice(
        ["severe", "moderate", "mild", "agitated_pace"],
        p=[0.25, 0.25, 0.30, 0.20]
    )
    t = np.arange(WINDOW_SEC)

    if variant == "severe":
        tremor_f = np.random.uniform(5, 9)
        tremor_a = np.random.uniform(1.2, 2.8)
        base_noise = 2.0
        n_spikes = np.random.randint(3, 8)
        spike_mag = (4, 10)
        base_hr = np.random.uniform(115, 150)
        hr_noise = 10
        max_steps = 3

    elif variant == "moderate":
        tremor_f = np.random.uniform(3, 6)
        tremor_a = np.random.uniform(0.5, 1.5)
        base_noise = 1.2
        n_spikes = np.random.randint(1, 5)
        spike_mag = (2, 6)
        base_hr = np.random.uniform(95, 120)
        hr_noise = 7
        max_steps = 8

    elif variant == "mild":
        # HR 80-105 — overlaps normal housework (78-100), exercise (90-115), anxious (85-105)
        tremor_f = np.random.uniform(2, 5)
        tremor_a = np.random.uniform(0.1, 0.6)
        base_noise = 0.5
        n_spikes = np.random.randint(0, 3)
        spike_mag = (1, 3)
        base_hr = np.random.uniform(80, 105)
        hr_noise = 4
        max_steps = 12

    else:  # agitated_pace
        tremor_f = np.random.uniform(1.5, 3)
        tremor_a = np.random.uniform(0.3, 1.0)
        base_noise = 0.8
        n_spikes = np.random.randint(1, 4)
        spike_mag = (2, 5)
        base_hr = np.random.uniform(88, 115)
        hr_noise = 6
        max_steps = 25

    # Tremor pattern
    ax = tremor_a * np.sin(2 * np.pi * tremor_f * t) + np.random.normal(0, base_noise, WINDOW_SEC)
    ay = tremor_a * 0.7 * np.cos(2 * np.pi * tremor_f * 1.3 * t) + np.random.normal(0, base_noise * 0.8, WINDOW_SEC)
    az = 9.8 + np.random.normal(0, base_noise * 0.4, WINDOW_SEC)

    for _ in range(n_spikes):
        st = np.random.randint(0, WINDOW_SEC)
        ax[st] += np.random.uniform(*spike_mag) * np.random.choice([-1, 1])
        ay[st] += np.random.uniform(spike_mag[0]*0.5, spike_mag[1]*0.7) * np.random.choice([-1, 1])

    # Agitated pacing: walk-like periodicity on top of tremor
    if variant == "agitated_pace":
        walk_f = np.random.uniform(1.0, 1.8)
        walk_a = np.random.uniform(0.4, 1.2)
        ax += walk_a * np.sin(2 * np.pi * walk_f * t)
        ay += walk_a * 0.4 * np.cos(2 * np.pi * walk_f * t)

    hr = base_hr + np.random.normal(0, hr_noise, WINDOW_SEC)
    for _ in range(np.random.randint(0, 4)):
        hr[np.random.randint(0, WINDOW_SEC)] += np.random.uniform(5, 15)
    hr = np.clip(hr, 58, 180)

    steps = np.zeros(WINDOW_SEC, dtype=int)
    if variant == "agitated_pace":
        n_bursts = np.random.randint(2, 6)
        for _ in range(n_bursts):
            b_start = np.random.randint(0, WINDOW_SEC - 4)
            b_dur = np.random.randint(2, 6)
            for j in range(b_start, min(b_start + b_dur, WINDOW_SEC)):
                steps[j] = np.random.randint(1, 3)
    else:
        n_shuffle = np.random.randint(0, max_steps + 1)
        if n_shuffle > 0:
            idx = np.random.choice(WINDOW_SEC, min(n_shuffle, WINDOW_SEC), replace=False)
            steps[idx] = 1

    # GPS: at home
    lat = HOME_LAT + np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)
    lng = HOME_LNG + np.random.normal(0, GPS_NOISE_STD * DEG_PER_METER, WINDOW_SEC)

    return {"ax": ax, "ay": ay, "az": az, "hr": hr, "steps": steps, "lat": lat, "lng": lng}


# =====================================================
# FEATURE EXTRACTION
# =====================================================

def extract_features(w):
    """
    9 features from a 30s window.
    gps_drift_rate = average distance from HOME in meters.
    """
    mag = np.sqrt(w["ax"]**2 + w["ay"]**2 + w["az"]**2)

    distances = []
    for i in range(len(w["lat"])):
        dlat_m = (w["lat"][i] - HOME_LAT) / DEG_PER_METER
        dlng_m = (w["lng"][i] - HOME_LNG) / DEG_PER_METER * np.cos(np.radians(w["lat"][i]))
        distances.append(np.sqrt(dlat_m**2 + dlng_m**2))

    return {
        "accel_magnitude_mean": float(np.mean(mag)),
        "accel_magnitude_std": float(np.std(mag)),
        "accel_magnitude_max": float(np.max(mag)),
        "hr_mean": float(np.mean(w["hr"])),
        "hr_std": float(np.std(w["hr"])),
        "hr_delta": float(np.mean(w["hr"][-3:]) - np.mean(w["hr"][:3])),
        "step_count": int(np.sum(w["steps"])),
        "movement_continuity": float(np.mean(w["steps"] > 0)),
        "gps_drift_rate": float(np.mean(distances)),
    }


# =====================================================
# MAIN
# =====================================================

GENERATORS = {
    0: ("Normal", _gen_normal),
    1: ("Fall", _gen_fall),
    2: ("Wandering", _gen_wandering),
    3: ("Distress", _gen_distress),
}

if __name__ == "__main__":
    print("=" * 60)
    print("  SahayAI Smartwatch Simulator v5 (Thick Boundary Overlap)")
    print("  10,000 samples (2,500 x 4 classes)")
    print("=" * 60)

    rows = []
    for label, (name, gen_fn) in GENERATORS.items():
        print(f"\nGenerating {SAMPLES_PER_CLASS} '{name}' windows...")
        for i in range(SAMPLES_PER_CLASS):
            window = gen_fn()
            feats = extract_features(window)
            feats["label"] = label
            rows.append(feats)
            if (i + 1) % 500 == 0:
                print(f"  {i+1}/{SAMPLES_PER_CLASS}")

    df = pd.DataFrame(rows).sample(frac=1, random_state=42).reset_index(drop=True)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, "backend", "data")
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "wearable_features.csv")
    df.to_csv(csv_path, index=False)

    print(f"\n{'=' * 60}")
    print(f"Saved to: {csv_path}")
    print(f"Total: {len(df)} | Features: {len(df.columns)-1}")