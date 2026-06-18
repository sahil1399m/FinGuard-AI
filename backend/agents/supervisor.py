DEBATE_THRESHOLD = 40  # risk score above this triggers the LLM debate


def should_debate(risk_score: int) -> bool:
    """Returns True if the transaction score warrants a Prosecution/Defense/Judge debate."""
    return risk_score >= DEBATE_THRESHOLD


def build_findings_summary(
    geo_result: dict,
    structuring_result: dict,
    behavioral_result: dict,
) -> list[dict]:
    """Packages rule-based agent results into a list for LLM consumption."""
    findings = []

    if geo_result.get("flagged"):
        findings.append({
            "agent":   "Geo-Velocity",
            "flagged": True,
            "reason":  geo_result["reason"],
            "details": geo_result.get("details", {}),
        })

    if structuring_result.get("flagged"):
        findings.append({
            "agent":   "Structuring",
            "flagged": True,
            "reason":  structuring_result["reason"],
            "details": structuring_result.get("details", {}),
        })

    if behavioral_result.get("flagged"):
        findings.append({
            "agent":   "Behavioral",
            "flagged": True,
            "reason":  behavioral_result["reason"],
            "details": behavioral_result.get("details", {}),
        })

    if not findings:
        findings.append({
            "agent":   "All rule-based agents",
            "flagged": False,
            "reason":  "No rule-based flags triggered.",
            "details": {},
        })

    return findings