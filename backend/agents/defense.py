import json
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

SYSTEM_PROMPT = """You are a Defense Counsel representing a bank customer accused of suspicious activity.
Your job is to build the STRONGEST POSSIBLE CASE that the transaction is legitimate and innocent.
Look for plausible innocent explanations — business payments, frequent travelers, one-time large purchases,
legitimate cash-intensive businesses, etc.

Analyze the transaction and respond ONLY with a valid JSON object.
No preamble, no markdown, no explanation outside the JSON.

Required JSON format:
{
  "argument": "Your detailed defense argument (2-4 sentences)",
  "confidence": <integer 0-100>,
  "innocent_explanations": ["explanation1", "explanation2"]
}"""


def run(transaction: dict, agent_findings: list[dict]) -> dict:
    """
    Calls Groq LLM to build the defense argument.
    Falls back gracefully if the API call fails.
    """
    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            api_key=os.getenv("GROQ_API_KEY"),
        )

        user_content = f"""
TRANSACTION DETAILS:
{json.dumps(transaction, indent=2)}

AGENT FINDINGS:
{json.dumps(agent_findings, indent=2)}

Build the strongest defense argument for why this transaction could be completely innocent and legitimate.
Respond ONLY with the JSON object.
"""
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ])

        raw = response.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        return {
            "argument":              result.get("argument", "No argument generated."),
            "confidence":            int(result.get("confidence", 50)),
            "innocent_explanations": result.get("innocent_explanations", []),
            "error":                 None,
        }

    except Exception as e:
        return {
            "argument":              f"Defense agent error: {str(e)}",
            "confidence":            0,
            "innocent_explanations": [],
            "error":                 str(e),
        }