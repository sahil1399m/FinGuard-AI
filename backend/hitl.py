"""
Human-in-the-Loop (HITL) queue.

When the judge is uncertain, the transaction is saved here and PAUSED.
A compliance officer reviews the full case report in the dashboard and
submits a final decision: LEGITIMATE or FLAGGED.
"""

import aiosqlite
from datetime import datetime, timezone

DB_PATH = "aml_auditor.db"

CREATE_HITL_TABLE = """
CREATE TABLE IF NOT EXISTS pending_human_reviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id      TEXT NOT NULL UNIQUE,
    user_id             TEXT NOT NULL,
    amount_usd          REAL NOT NULL,
    location            TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    risk_score          INTEGER,

    geo_flagged         INTEGER DEFAULT 0,
    geo_reason          TEXT,
    structuring_flagged INTEGER DEFAULT 0,
    structuring_reason  TEXT,
    behavioral_flagged  INTEGER DEFAULT 0,
    behavioral_reason   TEXT,

    prosecution_arg     TEXT,
    prosecution_conf    INTEGER,
    defense_arg         TEXT,
    defense_conf        INTEGER,
    judge_reasoning     TEXT,

    hitl_trigger_reason TEXT,
    status              TEXT DEFAULT 'PENDING',
    human_decision      TEXT,
    human_notes         TEXT,
    decided_at          TEXT,
    created_at          TEXT NOT NULL
)
"""


async def init_hitl_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_HITL_TABLE)
        await db.commit()


async def save_pending_review(case: dict):
    """
    Save a transaction to the HITL queue.
    Called when the judge is not confident enough for an automatic verdict.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO pending_human_reviews (
                transaction_id, user_id, amount_usd, location, timestamp,
                risk_score,
                geo_flagged, geo_reason,
                structuring_flagged, structuring_reason,
                behavioral_flagged, behavioral_reason,
                prosecution_arg, prosecution_conf,
                defense_arg, defense_conf,
                judge_reasoning, hitl_trigger_reason,
                status, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                case["transaction_id"],
                case["user_id"],
                case["amount_usd"],
                case["location"],
                case["timestamp"],
                case["risk_score"],
                int(case.get("geo_flagged", False)),
                case.get("geo_reason", ""),
                int(case.get("structuring_flagged", False)),
                case.get("structuring_reason", ""),
                int(case.get("behavioral_flagged", False)),
                case.get("behavioral_reason", ""),
                case.get("prosecution_arg", ""),
                case.get("prosecution_conf", 0),
                case.get("defense_arg", ""),
                case.get("defense_conf", 0),
                case.get("judge_reasoning", ""),
                case.get("hitl_trigger_reason", ""),
                "PENDING",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        await db.commit()
    print(f"[HITL] ⏸  Case queued for human review: {case['transaction_id']}")


async def get_pending_reviews() -> list[dict]:
    """Returns all cases waiting for a human decision."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM pending_human_reviews
            WHERE status = 'PENDING'
            ORDER BY created_at DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_reviews(limit: int = 100) -> list[dict]:
    """Returns all reviews including decided ones."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM pending_human_reviews
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def submit_human_decision(
    transaction_id: str,
    decision: str,
    notes: str = "",
) -> dict:
    """
    Records the compliance officer's decision.

    decision must be either:
      'LEGITIMATE' → stored as CLEAN
      'FLAGGED'    → stored as FLAGGED

    FIX: Now also updates the verdicts table so the case shows up
    correctly in recent_verdicts after a human decides.
    """
    if decision not in ("LEGITIMATE", "FLAGGED"):
        return {"success": False, "error": "Decision must be LEGITIMATE or FLAGGED"}

    final_status = "CLEAN" if decision == "LEGITIMATE" else "FLAGGED"
    decided_at   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    async with aiosqlite.connect(DB_PATH) as db:
        # Mark the HITL queue row as decided
        await db.execute(
            """
            UPDATE pending_human_reviews
            SET status         = 'DECIDED',
                human_decision = ?,
                human_notes    = ?,
                decided_at     = ?
            WHERE transaction_id = ?
            """,
            (final_status, notes, decided_at, transaction_id),
        )

        # Update the main transactions table
        await db.execute(
            "UPDATE transactions SET status = ? WHERE transaction_id = ?",
            (final_status, transaction_id),
        )

        # FIX: Also update the verdicts table so recent_verdicts reflects
        # the human decision. The verdict row was inserted when the
        # transaction was first processed (even on the HITL path).
        await db.execute(
            """
            UPDATE verdicts
            SET final_verdict = ?,
                judge_verdict = ?,
                recommended_action = ?
            WHERE transaction_id = ?
            """,
            (
                final_status,
                final_status,
                f"Human compliance officer decision: {final_status}. Notes: {notes}" if notes
                else f"Human compliance officer decision: {final_status}.",
                transaction_id,
            ),
        )

        await db.commit()

    print(
        f"[HITL] ✅ Human decision recorded: {transaction_id} → {final_status} "
        f"| Notes: '{notes}'"
    )
    return {
        "success":        True,
        "transaction_id": transaction_id,
        "final_status":   final_status,
        "decided_at":     decided_at,
    }


# ── Trigger logic ──────────────────────────────────────────────────────────────
def should_trigger_hitl(
    judge_verdict:       str,
    prosecution_conf:    int,
    defense_conf:        int,
    risk_score:          int,
) -> tuple[bool, str]:
    """
    Returns (should_trigger: bool, reason: str).

    Three conditions — any one triggers HITL:
      1. Judge verdict is REVIEW (judge itself is uncertain)
      2. Both agents are nearly equally confident AND gap is small (true split)
      3. Risk score is in the grey zone (40–65)

    FIX: Condition 2 now also checks the confidence gap (must be ≤ 20).
    Previously, prosecution=90% + defense=46% would incorrectly trigger
    HITL despite prosecution clearly winning.
    """
    if judge_verdict == "REVIEW":
        return True, (
            f"Judge issued a REVIEW verdict — not confident enough to "
            f"auto-approve or auto-flag. Risk score: {risk_score}/100."
        )

    # FIX: gap check added — only a genuine split triggers HITL
    if prosecution_conf >= 45 and defense_conf >= 45:
        gap = abs(prosecution_conf - defense_conf)
        if gap <= 20:
            return True, (
                f"Agents are genuinely split: prosecution {prosecution_conf}% confident, "
                f"defense {defense_conf}% confident (gap: {gap}%). Human judgment required."
            )

    if 40 <= risk_score <= 65:
        return True, (
            f"Risk score {risk_score}/100 falls in the grey zone (40–65). "
            f"Insufficient certainty for automatic verdict."
        )

    return False, ""