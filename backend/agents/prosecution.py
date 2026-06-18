import json
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

SYSTEM_PROMPT = """You are a Senior AML Compliance Investigator at a major financial institution.
Your job is to build the STRONGEST POSSIBLE CASE that a given bank transaction is fraudulent or suspicious.
You are the prosecution. Assume the worst — your job is to protect the bank and the financial system.

Analyze the transaction and agent findings, then respond ONLY with a valid JSON object.
No preamble, no markdown, no explanation outside the JSON.

Required JSON format:
{
  "argument": "Your detailed prosecution argument (2-4 sentences)",
  "confidence": <integer 0-100>,
  "key_red_flags": ["flag1", "flag2", "flag3"]
}"""


def run(transaction: dict, agent_findings: list[dict]) -> dict:
    """
    Calls Groq LLM to build the prosecution argument.
    Falls back gracefully if the API call fails.
    """
    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            api_key=os.getenv("GROQ_API_KEY"),
        )

        user_content = f"""
TRANSACTION DETAILS:
{json.dumps(transaction, indent=2)}

AGENT FINDINGS:
{json.dumps(agent_findings, indent=2)}

Build the strongest prosecution argument for why this transaction is suspicious or fraudulent.
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
            "argument":      result.get("argument", "No argument generated."),
            "confidence":    int(result.get("confidence", 50)),
            "key_red_flags": result.get("key_red_flags", []),
            "error":         None,
        }

    except Exception as e:
        return {
            "argument":      f"Prosecution agent error: {str(e)}",
            "confidence":    0,
            "key_red_flags": [],
            "error":         str(e),
        }