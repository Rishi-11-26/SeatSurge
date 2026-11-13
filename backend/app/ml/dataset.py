"""
SeatSurge ML Bot Detection — Synthetic Labelled Session Dataset Generator.
==========================================================================
Generates realistic behavioural feature distributions for:
1. Legitimate Human Fans:
   - High inter-arrival variance (human jitter: 800ms - 3500ms).
   - Natural human reaction times for seat selection (1800ms - 6000ms).
   - Low burstiness ratio and low error rates.
   - Legitimate browser user-agent profiles.

2. Automated Scalper / Sniper Bots:
   - Superhuman speed (inter-arrival: 10ms - 150ms).
   - Near-zero variance (clockwork polling or tight retry loops).
   - Instantaneous hold attempts (< 300ms from queue/drop).
   - High burstiness and aggressive error retry patterns.
   - Scripted or headless client signatures.
"""

import numpy as np
import pandas as pd
from typing import Tuple

FEATURE_COLUMNS = [
    "requests_per_minute",
    "mean_inter_arrival_ms",
    "std_inter_arrival_ms",
    "hold_attempt_speed_ms",
    "burst_ratio",
    "session_age_seconds",
    "error_rate",
    "user_agent_bot_flag",
]


def generate_session_dataset(
    n_samples: int = 3000,
    bot_ratio: float = 0.5,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Generates a labelled DataFrame of user session features.
    n_samples: Total number of sessions to generate.
    bot_ratio: Proportion of sessions that are bots (default: 50% balanced).
    """
    rng = np.random.RandomState(random_state)
    n_bots = int(n_samples * bot_ratio)
    n_humans = n_samples - n_bots

    # ── 1. Human Sessions (label = 0) ──────────────────────────────────────────
    human_rpm = rng.normal(loc=15.0, scale=6.0, size=n_humans).clip(1, 45)
    human_mean_iat = rng.normal(loc=2200.0, scale=600.0, size=n_humans).clip(800, 6000)
    human_std_iat = rng.normal(loc=1200.0, scale=400.0, size=n_humans).clip(400, 4000)
    human_reaction_speed = rng.normal(loc=3200.0, scale=900.0, size=n_humans).clip(1200, 8000)
    human_burst = rng.beta(a=2, b=8, size=n_humans).clip(0.05, 0.45)
    human_age = rng.exponential(scale=180.0, size=n_humans).clip(15, 900)
    human_err = rng.beta(a=1, b=20, size=n_humans).clip(0.0, 0.20)
    human_ua_flag = rng.choice([0.0, 1.0], p=[0.98, 0.02], size=n_humans)

    humans_df = pd.DataFrame({
        "requests_per_minute": human_rpm,
        "mean_inter_arrival_ms": human_mean_iat,
        "std_inter_arrival_ms": human_std_iat,
        "hold_attempt_speed_ms": human_reaction_speed,
        "burst_ratio": human_burst,
        "session_age_seconds": human_age,
        "error_rate": human_err,
        "user_agent_bot_flag": human_ua_flag,
        "label": 0,
    })

    # ── 2. Bot Sessions (label = 1) ────────────────────────────────────────────
    bot_rpm = rng.normal(loc=95.0, scale=25.0, size=n_bots).clip(45, 300)
    bot_mean_iat = rng.normal(loc=85.0, scale=35.0, size=n_bots).clip(10, 250)
    bot_std_iat = rng.normal(loc=25.0, scale=18.0, size=n_bots).clip(2, 95)
    bot_reaction_speed = rng.normal(loc=120.0, scale=60.0, size=n_bots).clip(15, 350)
    bot_burst = rng.beta(a=7, b=3, size=n_bots).clip(0.55, 1.0)
    bot_age = rng.exponential(scale=35.0, size=n_bots).clip(2, 180)
    bot_err = rng.beta(a=5, b=5, size=n_bots).clip(0.20, 0.90)
    bot_ua_flag = rng.choice([0.0, 1.0], p=[0.25, 0.75], size=n_bots)

    bots_df = pd.DataFrame({
        "requests_per_minute": bot_rpm,
        "mean_inter_arrival_ms": bot_mean_iat,
        "std_inter_arrival_ms": bot_std_iat,
        "hold_attempt_speed_ms": bot_reaction_speed,
        "burst_ratio": bot_burst,
        "session_age_seconds": bot_age,
        "error_rate": bot_err,
        "user_agent_bot_flag": bot_ua_flag,
        "label": 1,
    })

    # Combine and shuffle
    df = pd.concat([humans_df, bots_df], ignore_index=True)
    df = df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)
    return df
