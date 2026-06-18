from geopy.distance import geodesic
from datetime import datetime, timezone

CITY_COORDS = {
    "Mumbai, IN":       (19.0760,  72.8777),
    "London, UK":       (51.5074,  -0.1278),
    "New York, US":     (40.7128, -74.0060),
    "Tokyo, JP":        (35.6762, 139.6503),
    "Dubai, AE":        (25.2048,  55.2708),
    "Sydney, AU":       (-33.8688, 151.2093),
    "Frankfurt, DE":    (50.1109,   8.6821),
    "Singapore, SG":    (1.3521,  103.8198),
    "São Paulo, BR":    (-23.5505, -46.6333),
    "Toronto, CA":      (43.6532,  -79.3832),
}

MAX_SPEED_KMH = 900  # commercial jet speed threshold


def _parse_time(iso_str: str) -> datetime | None:
    try:
        return datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return None


def run(transaction: dict) -> dict:
    """
    Checks if the required travel speed between the previous login location
    and the current transaction location exceeds MAX_SPEED_KMH.

    Returns:
        flagged (bool)
        reason (str)
        score_contribution (int)
        details (dict)
    """
    current_city = transaction.get("location", "")
    prev_login   = transaction.get("previous_login", {})
    prev_city    = prev_login.get("location", "")
    prev_time    = _parse_time(prev_login.get("time", ""))
    curr_time    = _parse_time(transaction.get("timestamp", ""))

    if not prev_city or not current_city:
        return _clean("Missing location data.")

    if prev_city == current_city:
        return _clean(f"Same city: {current_city}. No travel anomaly.")

    coords_curr = CITY_COORDS.get(current_city)
    coords_prev = CITY_COORDS.get(prev_city)

    if not coords_curr or not coords_prev:
        return _clean(f"Unknown city coordinates for '{current_city}' or '{prev_city}'.")

    if not prev_time or not curr_time:
        return _clean("Could not parse timestamps.")

    distance_km = geodesic(coords_prev, coords_curr).kilometers
    time_diff_hours = (curr_time - prev_time).total_seconds() / 3600

    if time_diff_hours <= 0:
        return _flag(
            f"Transaction timestamp is before or equal to previous login time. "
            f"Distance: {distance_km:.0f} km.",
            distance_km, 0, prev_city, current_city,
        )

    required_speed = distance_km / time_diff_hours

    if required_speed > MAX_SPEED_KMH:
        return _flag(
            f"Impossible travel detected. Previous login: {prev_city} "
            f"at {prev_login.get('time')}. Current location: {current_city}. "
            f"Distance: {distance_km:.0f} km in {time_diff_hours * 60:.1f} minutes "
            f"requires {required_speed:.0f} km/h "
            f"(limit: {MAX_SPEED_KMH} km/h).",
            distance_km, required_speed, prev_city, current_city,
        )

    return _clean(
        f"Travel plausible. {prev_city} → {current_city}: "
        f"{distance_km:.0f} km in {time_diff_hours * 60:.1f} min "
        f"= {required_speed:.0f} km/h."
    )


def _flag(reason, distance_km, speed, from_city, to_city):
    return {
        "flagged": True,
        "reason": reason,
        "score_contribution": 40,
        "details": {
            "from_city": from_city,
            "to_city": to_city,
            "distance_km": round(distance_km, 1),
            "required_speed_kmh": round(speed, 1),
            "threshold_kmh": MAX_SPEED_KMH,
        },
    }


def _clean(reason):
    return {
        "flagged": False,
        "reason": reason,
        "score_contribution": 0,
        "details": {},
    }