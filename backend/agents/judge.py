import json
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

SYSTEM_PROMPT = """You are the Chief Compliance Officer at a major financial institution acting as Judge.
You have received arguments from both the Prosecution (AML investigator) and the Defense (customer counsel).
Your job is to weigh both sides fairly and issue a final, binding compliance verdict.

You must choose ONE of three verdicts:
- FLAGGED   → Strong evidence of fraud/money laundering. Block the transaction, escalate to regulators.
- REVIEW    → Ambiguous evidence. Flag for human compliance officer review within 24 hours.
- CLEAN     → Insufficient evidence of wrongdoing. Allow the transaction to proceed.

Respond ONLY with a valid JSON object. No preamble, no markdown, no explanation outside the JSON.

Required JSON format:
{
  "verdict": "FLAGGED" | "REVIEW" | "CLEAN",
  "reasoning": "Your 2-4 sentence judicial reasoning explaining how you weighed both sides",
  "final_risk_score": <integer 0-100>,
  "recommended_action": "Specific action for compliance team"
}"""


def run(
    transaction: dict,
    prosecution_result: dict,
    defense_result: dict,
    current_risk_score: int,
) -> dict:
    """
    Calls Groq LLM to issue the final verdict after reading prosecution and defense arguments.
    Falls back gracefully if the API call fails.
    """
    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            api_key=os.getenv("GROQ_API_KEY"),
        )

        user_content = f"""
TRANSACTION:
{json.dumps(transaction, indent=2)}

CURRENT RISK SCORE (from rule-based agents): {current_risk_score}/100

PROSECUTION ARGUMENT:
{prosecution_result.get('argument', 'N/A')}
Prosecution confidence: {prosecution_result.get('confidence', 0)}%
Red flags cited: {prosecution_result.get('key_red_flags', [])}

DEFENSE ARGUMENT:
{defense_result.get('argument', 'N/A')}
Defense confidence: {defense_result.get('confidence', 0)}%
Innocent explanations offered: {defense_result.get('innocent_explanations', [])}

Issue your final compliance verdict. Respond ONLY with the JSON object.
"""
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ])

        raw = response.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        verdict = result.get("verdict", "REVIEW")
        if verdict not in ("FLAGGED", "REVIEW", "CLEAN"):
            verdict = "REVIEW"

        return {
            "verdict":              verdict,
            "reasoning":            result.get("reasoning", "No reasoning provided."),
            "final_risk_score":     int(result.get("final_risk_score", current_risk_score)),
            "recommended_action":   result.get("recommended_action", "Manual review required."),
            "error":                None,
        }

    except Exception as e:
        return {
            "verdict":            "REVIEW",
            "reasoning":          f"Judge agent error — defaulting to manual review: {str(e)}",
            "final_risk_score":   current_risk_score,
            "recommended_action": "Manual review required due to system error.",
            "error":              str(e),
        }