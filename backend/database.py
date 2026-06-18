import aiosqlite
import json
from datetime import datetime, timezone

DB_PATH = "aml_auditor.db"

CREATE_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  TEXT NOT NULL UNIQUE,
    user_id         TEXT NOT NULL,
    amount_usd      REAL NOT NULL,
    location        TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    previous_login  TEXT NOT NULL,
    scenario        TEXT,
    ring_id         TEXT,
    risk_score      INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'PENDING',
    inserted_at     TEXT NOT NULL
)
"""

CREATE_VERDICTS = """
CREATE TABLE IF NOT EXISTS verdicts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id      TEXT NOT NULL,
    user_id             TEXT NOT NULL,
    risk_score          INTEGER,
    status              TEXT,
    geo_flagged         INTEGER DEFAULT 0,
    geo_reason          TEXT,
    structuring_flagged INTEGER DEFAULT 0,
    structuring_reason  TEXT,
    behavioral_flagged  INTEGER DEFAULT 0,
    behavioral_reason   TEXT,
    prosecution_arg     TEXT,
    defense_arg         TEXT,
    judge_verdict       TEXT,
    judge_reasoning     TEXT,
    created_at          TEXT NOT NULL
)
"""

# ── WAL mode helper — call this on every connection ───────────────────────────
async def _apply_pragmas(db):
    """
    WAL mode = multiple readers never block each other.
    busy_timeout = wait up to 10 seconds if DB is locked instead of crashing.
    This fixes the 'backend offline' issue caused by SQLite write locks.
    """
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=10000")
    await db.execute("PRAGMA synchronous=NORMAL")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        await db.execute(CREATE_TRANSACTIONS)
        await db.execute(CREATE_VERDICTS)
        await db.commit()
    print("[DB] Tables initialised (WAL mode enabled).")


async def insert_transaction(txn: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        await db.execute(
            """INSERT OR IGNORE INTO transactions
               (transaction_id,user_id,amount_usd,location,timestamp,
                previous_login,scenario,ring_id,inserted_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (txn["transaction_id"], txn["user_id"], txn["amount_usd"],
             txn["location"], txn["timestamp"],
             json.dumps(txn.get("previous_login", {})),
             txn.get("scenario"), txn.get("ring_id"),
             datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        await db.commit()


async def update_transaction_verdict(transaction_id: str, risk_score: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        await db.execute(
            "UPDATE transactions SET risk_score=?,status=? WHERE transaction_id=?",
            (risk_score, status, transaction_id),
        )
        await db.commit()


async def insert_verdict(verdict: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        await db.execute(
            """INSERT INTO verdicts
               (transaction_id,user_id,risk_score,status,
                geo_flagged,geo_reason,structuring_flagged,structuring_reason,
                behavioral_flagged,behavioral_reason,
                prosecution_arg,defense_arg,judge_verdict,judge_reasoning,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (verdict.get("transaction_id"), verdict.get("user_id"),
             verdict.get("risk_score"), verdict.get("status"),
             int(verdict.get("geo_flagged", False)), verdict.get("geo_reason"),
             int(verdict.get("structuring_flagged", False)), verdict.get("structuring_reason"),
             int(verdict.get("behavioral_flagged", False)), verdict.get("behavioral_reason"),
             verdict.get("prosecution_arg"), verdict.get("defense_arg"),
             verdict.get("judge_verdict"), verdict.get("judge_reasoning"),
             datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        await db.commit()


async def get_user_history(user_id: str, limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT amount_usd,location,timestamp,risk_score,status
               FROM transactions WHERE user_id=?
               ORDER BY inserted_at DESC LIMIT ?""",
            (user_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_recent_verdicts(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM verdicts ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_flagged_users(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        await _apply_pragmas(db)
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT user_id,transaction_id,amount_usd,location,timestamp,ring_id
               FROM transactions WHERE status IN ('FLAGGED','REVIEW')
               ORDER BY inserted_at DESC LIMIT ?""",
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]