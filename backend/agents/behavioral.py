import statistics

Z_SCORE_THRESHOLD   = 3.0   # flag if 3 standard deviations above mean
MIN_HISTORY_RECORDS = 5     # need at least 5 past txns to establish a baseline
SPIKE_MULTIPLIER    = 5.0   # flag if amount > 5x user average (fallback)


def run(transaction: dict, user_history: list[dict]) -> dict:
    """
    Flags a transaction if the amount is a statistical outlier relative to
    the user's historical spending pattern.

    Uses z-score when enough history exists, falls back to a simple
    multiplier check otherwise.

    Returns:
        flagged (bool)
        reason (str)
        score_contribution (int)
        details (dict)
    """
    amount  = transaction.get("amount_usd", 0.0)
    user_id = transaction.get("user_id", "unknown")

    if not user_history:
        return _clean(
            f"No transaction history found for {user_id}. "
            "Cannot establish a baseline — skipping behavioral check."
        )

    past_amounts = [h["amount_usd"] for h in user_history if h.get("amount_usd")]

    if len(past_amounts) < MIN_HISTORY_RECORDS:
        avg = sum(past_amounts) / len(past_amounts) if past_amounts else 0
        if avg > 0 and amount > avg * SPIKE_MULTIPLIER:
            return _flag(
                f"Amount ${amount:,.2f} is {amount / avg:.1f}x user's average "
                f"(${avg:,.2f}) based on {len(past_amounts)} prior transactions. "
                f"Insufficient history for z-score — using spike multiplier.",
                amount, avg, None, len(past_amounts), amount / avg,
            )
        return _clean(
            f"Insufficient history ({len(past_amounts)} records, need {MIN_HISTORY_RECORDS}). "
            f"No spike detected vs average ${sum(past_amounts)/max(len(past_amounts),1):,.2f}."
        )

    mean   = statistics.mean(past_amounts)
    stdev  = statistics.stdev(past_amounts)

    if stdev == 0:
        if amount == mean:
            return _clean(f"Amount matches user's fixed spend pattern exactly (${mean:,.2f}).")
        z_score = float("inf")
    else:
        z_score = (amount - mean) / stdev

    if z_score >= Z_SCORE_THRESHOLD:
        return _flag(
            f"Behavioral anomaly detected. Amount ${amount:,.2f} is {z_score:.1f} standard "
            f"deviations above {user_id}'s 30-day mean of ${mean:,.2f} "
            f"(σ = ${stdev:,.2f}). This is statistically extreme.",
            amount, mean, stdev, len(past_amounts), z_score,
        )

    return _clean(
        f"Amount ${amount:,.2f} within normal range for {user_id}. "
        f"Mean: ${mean:,.2f}, σ: ${stdev:,.2f}, z-score: {z_score:.2f}."
    )


def _flag(reason, amount, mean, stdev, history_len, z_or_multiplier):
    return {
        "flagged": True,
        "reason": reason,
        "score_contribution": 15,
        "details": {
            "amount": amount,
            "user_mean": round(mean, 2),
            "user_stdev": round(stdev, 2) if stdev is not None else None,
            "z_score": round(z_or_multiplier, 2),
            "history_records_used": history_len,
        },
    }


def _clean(reason):
    return {
        "flagged": False,
        "reason": reason,
        "score_contribution": 0,
        "details": {},
    }