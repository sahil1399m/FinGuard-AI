STRUCTURING_LOWER = 9_000
STRUCTURING_UPPER = 9_999
IRS_THRESHOLD     = 10_000


def run(transaction: dict, user_history: list[dict] | None = None) -> dict:
    """
    Detects structuring (smurfing) — transactions just below the $10,000
    IRS mandatory reporting threshold.

    Also checks for repeated sub-threshold transactions from the same user
    in recent history (smurfing pattern).

    Returns:
        flagged (bool)
        reason (str)
        score_contribution (int)
        details (dict)
    """
    amount = transaction.get("amount_usd", 0.0)
    user   = transaction.get("user_id", "unknown")

    in_band = STRUCTURING_LOWER <= amount <= STRUCTURING_UPPER

    # Check recent history for repeated structuring attempts
    smurf_count = 0
    if user_history:
        smurf_count = sum(
            1 for h in user_history
            if STRUCTURING_LOWER <= h.get("amount_usd", 0) <= STRUCTURING_UPPER
        )

    if in_band:
        pct_below = ((IRS_THRESHOLD - amount) / IRS_THRESHOLD) * 100

        if smurf_count >= 2:
            reason = (
                f"Structuring detected. Amount ${amount:,.2f} is {pct_below:.1f}% "
                f"below the ${IRS_THRESHOLD:,} IRS reporting threshold. "
                f"User {user} has {smurf_count} prior transactions in the same band "
                f"— classic smurfing pattern."
            )
        else:
            reason = (
                f"Amount ${amount:,.2f} falls in the structuring band "
                f"(${STRUCTURING_LOWER:,}–${STRUCTURING_UPPER:,}), "
                f"{pct_below:.1f}% below the ${IRS_THRESHOLD:,} reporting limit."
            )

        return {
            "flagged": True,
            "reason": reason,
            "score_contribution": 35 if amount >= 9_800 else (30 if amount >= 9_500 else 25),
            "details": {
                "amount": amount,
                "lower_bound": STRUCTURING_LOWER,
                "upper_bound": STRUCTURING_UPPER,
                "irs_threshold": IRS_THRESHOLD,
                "pct_below_threshold": round(pct_below, 2),
                "prior_structuring_count": smurf_count,
            },
        }

    return {
        "flagged": False,
        "reason": f"Amount ${amount:,.2f} is outside the structuring band. No structuring detected.",
        "score_contribution": 0,
        "details": {"amount": amount},
    }