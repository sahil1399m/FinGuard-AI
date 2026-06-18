from datetime import datetime, timezone


def compute_risk_score(
    geo_flagged: bool = False,
    structuring_flagged: bool = False,
    behavioral_flagged: bool = False,
    amount_usd: float = 0.0,
    timestamp: str = "",
) -> dict:
    """
    Returns a risk score between 0 and 100.

    Weights:
        Geo-velocity flag         → up to 40 pts
        Structuring flag          → up to 35 pts
        Behavioral deviation      → up to 15 pts
        Night-hours anomaly       → up to 10 pts
    """
    score = 0
    breakdown = {}

    # --- Geo-velocity (40 pts) ---
    geo_pts = 40 if geo_flagged else 0
    score += geo_pts
    breakdown["geo_velocity"] = geo_pts

    # --- Structuring (35 pts) ---
    # Extra weight if amount is extremely close to the $10k limit
    if structuring_flagged:
        if amount_usd >= 9_800:
            struct_pts = 35
        elif amount_usd >= 9_500:
            struct_pts = 30
        else:
            struct_pts = 25
    else:
        struct_pts = 0
    score += struct_pts
    breakdown["structuring"] = struct_pts

    # --- Behavioral deviation (15 pts) ---
    behavioral_pts = 15 if behavioral_flagged else 0
    score += behavioral_pts
    breakdown["behavioral"] = behavioral_pts

    # --- Night-hours anomaly (10 pts) ---
    night_pts = 0
    if timestamp:
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            hour = dt.hour
            if 2 <= hour <= 5:
                night_pts = 10
            elif hour == 1 or hour == 6:
                night_pts = 5
        except ValueError:
            pass
    score += night_pts
    breakdown["night_hours"] = night_pts

    score = min(score, 100)

    if score >= 60:
        status = "FLAGGED"
    elif score >= 30:
        status = "REVIEW"
    else:
        status = "CLEAN"

    return {
        "risk_score": score,
        "status": status,
        "breakdown": breakdown,
    }


def score_to_label(score: int) -> str:
    if score >= 60:
        return "HIGH RISK"
    elif score >= 30:
        return "MEDIUM RISK"
    else:
        return "LOW RISK"