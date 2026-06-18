import json
import asyncio
import threading
import queue
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from backend.database import (
    init_db, insert_transaction, insert_verdict,
    update_transaction_verdict, get_user_history,
    get_recent_verdicts, get_flagged_users,
)
from backend.graph.aml_graph import run_aml_pipeline
from backend.network.tx_graph import build_fraud_graph, graph_to_pyvis_html

# ── In-memory store (deque ops are atomic under the GIL — thread-safe) ────────
verdict_store: deque = deque(maxlen=50)

# ── Thread-safe handoff: API thread → worker thread ────────────────────────────
transaction_queue: "queue.Queue" = queue.Queue()

# ── Reference to the MAIN event loop, captured at startup ─────────────────────
main_event_loop: asyncio.AbstractEventLoop | None = None


# ── WebSocket manager ──────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        print(f"[WS] Client connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        print(f"[WS] Client disconnected. Total: {len(self.active)}")

    async def broadcast(self, data: dict):
        payload = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)


manager = ConnectionManager()


# ── Worker thread — keeps the API responsive no matter how slow Groq is ───────
def _worker_thread_main():
    """
    Runs forever in its own OS thread with its own asyncio event loop,
    completely separate from the FastAPI/uvicorn main event loop.

    The Groq LLM calls (prosecution/defense/judge) are slow. If they ran on
    the same event loop as the API, several piling up would freeze
    GET /health and make the dashboard show 'Backend offline' — which is
    the exact symptom you saw. This thread processes transactions ONE AT A
    TIME, fully isolated, so the API never waits on it.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def process_one(txn_dict: dict):
        try:
            user_history = await get_user_history(txn_dict["user_id"], limit=30)
            final_state  = await run_aml_pipeline(txn_dict, user_history)

            verdict = {
                "transaction_id":      txn_dict["transaction_id"],
                "user_id":             txn_dict["user_id"],
                "amount_usd":          txn_dict["amount_usd"],
                "location":            txn_dict["location"],
                "timestamp":           txn_dict["timestamp"],
                "scenario":            txn_dict.get("scenario"),

                "risk_score":          final_state["risk_score"],
                "final_risk_score":    final_state["final_risk_score"],
                "status":              final_state["status"],
                "final_verdict":       final_state["final_verdict"],
                "breakdown":           final_state["breakdown"],

                "geo_flagged":         final_state["geo_result"].get("flagged", False),
                "geo_reason":          final_state["geo_result"].get("reason", ""),
                "structuring_flagged": final_state["structuring_result"].get("flagged", False),
                "structuring_reason":  final_state["structuring_result"].get("reason", ""),
                "behavioral_flagged":  final_state["behavioral_result"].get("flagged", False),
                "behavioral_reason":   final_state["behavioral_result"].get("reason", ""),

                "prosecution_arg":     final_state.get("prosecution_result", {}).get("argument", ""),
                "defense_arg":         final_state.get("defense_result",     {}).get("argument", ""),
                "judge_verdict":       final_state.get("judge_result",       {}).get("verdict",   ""),
                "judge_reasoning":     final_state["final_reasoning"],
                "recommended_action":  final_state["recommended_action"],

                "processed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

            await update_transaction_verdict(
                txn_dict["transaction_id"],
                verdict["final_risk_score"],
                verdict["final_verdict"],
            )
            await insert_verdict(verdict)

            verdict_store.appendleft(verdict)

            if main_event_loop is not None:
                asyncio.run_coroutine_threadsafe(manager.broadcast(verdict), main_event_loop)

            color = (
                "\033[91m" if verdict["final_verdict"] == "FLAGGED" else
                "\033[93m" if verdict["final_verdict"] == "REVIEW"  else
                "\033[92m"
            )
            print(f"[VERDICT] {color}{verdict['final_verdict']}\033[0m  "
                  f"score={verdict['final_risk_score']}  {txn_dict['transaction_id']}  "
                  f"(queue: {transaction_queue.qsize()} waiting)")

        except Exception as e:
            print(f"[ERROR] Worker failed for {txn_dict.get('transaction_id')}: {e}")

    print("[WORKER] Background processing thread started — fully isolated from API.")
    while True:
        txn_dict = transaction_queue.get()
        loop.run_until_complete(process_one(txn_dict))


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_event_loop
    main_event_loop = asyncio.get_event_loop()

    await init_db()

    worker = threading.Thread(target=_worker_thread_main, daemon=True)
    worker.start()

    print("[APP] AML Auditor backend started.")
    yield
    print("[APP] AML Auditor backend shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AML Auditor API",
    description="Multi-Agent AML detection — worker-thread architecture, no HITL",
    version="3.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Schemas ────────────────────────────────────────────────────────────────────
class Transaction(BaseModel):
    transaction_id: str
    user_id:        str
    amount_usd:     float
    location:       str
    timestamp:      str
    previous_login: dict
    scenario:       str | None = None
    ring_id:        str | None = None


# ── Main endpoint — ALWAYS instant ─────────────────────────────────────────────
@app.post("/audit_transaction")
async def audit_transaction(txn: Transaction):
    txn_dict = txn.model_dump()
    await insert_transaction(txn_dict)

    print(f"\n[TXN] {txn.transaction_id} | {txn.user_id} | "
          f"${txn.amount_usd:,.2f} | {txn.location} | {txn.scenario}")

    transaction_queue.put(txn_dict)

    return {
        "status": "queued",
        "transaction_id": txn.transaction_id,
        "queue_position": transaction_queue.qsize(),
    }


# ── REST endpoints — always fast, never blocked by AI processing ──────────────
@app.get("/results")
async def get_results():
    return {"results": list(verdict_store)}

@app.get("/recent_verdicts")
async def recent_verdicts(limit: int = 50):
    return {"verdicts": await get_recent_verdicts(limit)}

@app.get("/fraud_graph")
async def fraud_graph():
    flagged    = await get_flagged_users(limit=100)
    graph_data = build_fraud_graph(flagged)
    return {"graph_data": graph_data, "html": graph_to_pyvis_html(graph_data)}

@app.get("/health")
async def health():
    return {
        "status":             "ok",
        "verdicts_in_memory": len(verdict_store),
        "websocket_clients":  len(manager.active),
        "queue_size":         transaction_queue.qsize(),
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    if verdict_store:
        await ws.send_text(json.dumps(list(verdict_store)[0]))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)