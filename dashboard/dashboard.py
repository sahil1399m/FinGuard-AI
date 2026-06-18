import streamlit as st
import requests
import time
import plotly.graph_objects as go
from collections import deque

st.set_page_config(
    page_title="AML Auditor — Control Room",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKEND = "http://localhost:8000"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;700;800&display=swap');
html, body, [class*="css"] { font-family:'Syne',sans-serif; background-color:#0a0c10; color:#e2e8f0; }
.stApp { background-color:#0a0c10; }
.block-container { padding:1.5rem 2rem; max-width:100%; }

.control-header { display:flex; align-items:center; gap:16px; padding:16px 24px;
  background:linear-gradient(135deg,#0d1117 0%,#161b27 100%);
  border:1px solid #1e2a3a; border-radius:12px; margin-bottom:20px; }
.header-dot { width:10px; height:10px; border-radius:50%; background:#22c55e;
  box-shadow:0 0 8px #22c55e; animation:pulse-dot 2s infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:.4} }
.header-title { font-size:22px; font-weight:800; color:#f1f5f9; letter-spacing:-.5px; margin:0; }
.header-sub   { font-size:12px; color:#64748b; font-family:'JetBrains Mono',monospace; margin:0; }

.metric-row { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px; }
.metric-card { background:#0d1117; border:1px solid #1e2a3a; border-radius:10px; padding:14px 18px; }
.metric-label { font-size:11px; font-weight:600; color:#475569; text-transform:uppercase; letter-spacing:.08em; margin-bottom:6px; }
.metric-value { font-size:28px; font-weight:800; font-family:'JetBrains Mono',monospace; line-height:1; }
.metric-value.green  { color:#22c55e; }
.metric-value.red    { color:#ef4444; }
.metric-value.amber  { color:#f59e0b; }
.metric-value.blue   { color:#3b82f6; }

.txn-item { display:flex; justify-content:space-between; align-items:flex-start;
  padding:10px 12px; border-radius:8px; margin-bottom:8px;
  border-left:3px solid transparent; background:#131820;
  font-family:'JetBrains Mono',monospace; font-size:11px; }
.txn-item.flagged { border-left-color:#ef4444; background:#1a1012; }
.txn-item.review  { border-left-color:#f59e0b; background:#171410; }
.txn-item.clean   { border-left-color:#22c55e; background:#0f1710; }

.verdict-badge { font-size:10px; font-weight:700; padding:2px 8px; border-radius:20px; letter-spacing:.05em; }
.verdict-badge.FLAGGED { background:#450a0a; color:#ef4444; }
.verdict-badge.REVIEW  { background:#451a00; color:#f59e0b; }
.verdict-badge.CLEAN   { background:#052e16; color:#22c55e; }

.debate-box { padding:12px 14px; border-radius:8px; margin-bottom:10px; font-size:12px; line-height:1.6; }
.debate-box.prosecution { background:#1a0f0f; border:1px solid #7f1d1d; }
.debate-box.defense     { background:#0f1a13; border:1px solid #14532d; }
.debate-box.judge       { background:#0f1020; border:1px solid #1e3a8a; }
.debate-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.1em; margin-bottom:6px; }
.debate-label.prosecution { color:#ef4444; }
.debate-label.defense     { color:#22c55e; }
.debate-label.judge       { color:#60a5fa; }
.debate-text  { color:#cbd5e1; }

.score-bar-bg   { height:6px; border-radius:3px; background:#1e2a3a; margin:8px 0 4px; }
.score-bar-fill { height:6px; border-radius:3px; transition:width .5s ease; }

.agent-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid #1e2a3a; font-size:12px; }
.agent-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
.agent-dot.active   { background:#ef4444; box-shadow:0 0 6px #ef4444; }
.agent-dot.inactive { background:#1e2a3a; }
.agent-name   { color:#64748b; font-weight:600; flex:1; }
.agent-reason { color:#94a3b8; font-size:11px; }

.feed-scroll { max-height:420px; overflow-y:auto; scrollbar-width:thin; scrollbar-color:#1e2a3a transparent; }
.section-title { font-size:11px; font-weight:700; color:#475569; text-transform:uppercase;
  letter-spacing:.1em; border-bottom:1px solid #1e2a3a; padding-bottom:8px; margin-bottom:12px; }

div[data-testid="stSidebar"] { background:#0d1117; border-right:1px solid #1e2a3a; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for key, val in [
    ("verdicts", deque(maxlen=50)), ("total", 0), ("flagged", 0),
    ("review", 0), ("scores", deque(maxlen=50)),
    ("health_cache", {}), ("health_fail_count", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── Helpers ────────────────────────────────────────────────────────────────────
def get(url, timeout=5):
    try:
        r = requests.get(f"{BACKEND}{url}", timeout=timeout)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def get_health():
    """Sticky-cache health check — only shows offline after 3 consecutive failures,
    so a single slow response doesn't flash a false 'offline' message."""
    try:
        r = requests.get(f"{BACKEND}/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            st.session_state.health_cache      = data
            st.session_state.health_fail_count = 0
            return data
        raise ConnectionError("non-200")
    except Exception:
        st.session_state.health_fail_count += 1
        if st.session_state.health_fail_count <= 3 and st.session_state.health_cache:
            return st.session_state.health_cache
        return {}

def score_color(s):
    return "#ef4444" if s >= 60 else "#f59e0b" if s >= 30 else "#22c55e"

def vclass(v):
    v = str(v).upper()
    if v == "FLAGGED": return "flagged"
    if v == "REVIEW":  return "review"
    return "clean"

def txn_html(v):
    verdict = str(v.get("final_verdict", v.get("status", "CLEAN"))).upper()
    css     = vclass(verdict)
    score   = v.get("final_risk_score", v.get("risk_score", 0))
    bc      = score_color(score)
    ts      = v.get("timestamp", "")[:16].replace("T", " ")
    return f"""<div class="txn-item {css}">
  <div style="flex:1;min-width:0">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
      <span style="color:#60a5fa;font-weight:600">{v.get('user_id','?')}</span>
      <span style="color:#94a3b8;font-size:10px">{v.get('transaction_id','?')}</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#f1f5f9;font-weight:600">${v.get('amount_usd',0):,.2f}</span>
      <span style="color:#94a3b8;font-size:10px">{v.get('location','?')}</span>
    </div>
    <div class="score-bar-bg"><div class="score-bar-fill" style="width:{score}%;background:{bc}"></div></div>
    <span style="font-size:10px;color:{bc}">{score}/100</span>
  </div>
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;margin-left:12px">
    <span class="verdict-badge {verdict}">{verdict}</span>
    <span style="font-size:10px;color:#475569">{ts}</span>
  </div>
</div>"""

def debate_html(v):
    html = ""
    if v.get("prosecution_arg"):
        html += f'<div class="debate-box prosecution"><div class="debate-label prosecution">⚖ Prosecution</div><div class="debate-text">{v["prosecution_arg"]}</div></div>'
    if v.get("defense_arg"):
        html += f'<div class="debate-box defense"><div class="debate-label defense">🛡 Defense</div><div class="debate-text">{v["defense_arg"]}</div></div>'
    if v.get("judge_reasoning"):
        jv = str(v.get("judge_verdict", v.get("final_verdict", ""))).upper()
        html += f'<div class="debate-box judge"><div class="debate-label judge">⚖ Judge — {jv}</div><div class="debate-text">{v["judge_reasoning"]}</div></div>'
    return html or "<div style='color:#475569;font-size:12px;padding:8px'>No debate — score below threshold (rule-based verdict only)</div>"

def agents_html(v):
    rows = [
        ("Geo-Velocity", v.get("geo_flagged", False),        v.get("geo_reason", "")),
        ("Structuring",  v.get("structuring_flagged", False), v.get("structuring_reason", "")),
        ("Behavioral",   v.get("behavioral_flagged", False),  v.get("behavioral_reason", "")),
    ]
    html = ""
    for name, flagged, reason in rows:
        dot   = "active" if flagged else "inactive"
        short = (reason[:80] + "…") if len(reason) > 80 else reason
        html += f'<div class="agent-row"><div class="agent-dot {dot}"></div><span class="agent-name">{name}</span><span class="agent-reason">{"🚨 "+short if flagged else "✓ Clear"}</span></div>'
    return html

def make_gauge(score):
    c   = score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number={"font": {"size": 36, "color": c, "family": "JetBrains Mono"}},
        gauge={
            "axis":      {"range": [0, 100], "tickwidth": 1, "tickcolor": "#1e2a3a", "tickfont": {"color": "#475569", "size": 10}},
            "bar":       {"color": c, "thickness": 0.25},
            "bgcolor":   "#0d1117", "borderwidth": 0,
            "steps":     [{"range": [0, 30], "color": "#0a1a0f"}, {"range": [30, 60], "color": "#1a1400"}, {"range": [60, 100], "color": "#1a0a0a"}],
            "threshold": {"line": {"color": c, "width": 3}, "thickness": 0.8, "value": score},
        }
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=20, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#94a3b8"})
    return fig

def make_timeline(scores):
    if not scores:
        scores = [0]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=list(scores), mode="lines+markers",
        line=dict(color="#3b82f6", width=2),
        marker=dict(color=[score_color(s) for s in scores], size=6),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
    ))
    fig.add_hline(y=60, line_dash="dash", line_color="#ef4444", line_width=1, opacity=0.5)
    fig.add_hline(y=30, line_dash="dash", line_color="#f59e0b", line_width=1, opacity=0.5)
    fig.update_layout(
        height=150, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(range=[0, 105], showgrid=True, gridcolor="#1e2a3a", zeroline=False,
                   tickfont={"size": 10, "color": "#475569"}),
        showlegend=False,
    )
    return fig

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='font-size:16px;font-weight:800;color:#f1f5f9;margin-bottom:4px'>🏦 AML Auditor</div>"
        "<div style='font-size:11px;color:#475569;font-family:JetBrains Mono,monospace;margin-bottom:20px'>CONTROL ROOM v1.0</div>",
        unsafe_allow_html=True,
    )
    st.markdown("**⚙️ Settings**")
    refresh_rate = st.slider("Refresh rate (seconds)", 2, 10, 3)
    st.markdown("---")
    st.markdown("**📡 Backend Status**")
    health = get_health()
    if health.get("status") == "ok":
        st.markdown(
            f"<div style='font-size:12px;color:#22c55e'>● Connected</div>"
            f"<div style='font-size:11px;color:#475569;margin-top:4px'>"
            f"Verdicts: {health.get('verdicts_in_memory', 0)}<br>"
            f"WS clients: {health.get('websocket_clients', 0)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='font-size:12px;color:#ef4444'>● Backend offline — start uvicorn first</div>",
            unsafe_allow_html=True,
        )
    st.markdown("---")
    st.markdown("**🔍 Filter**")
    filter_verdict = st.selectbox(
        "Filter by verdict",
        ["All", "FLAGGED", "REVIEW", "CLEAN"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        "<div style='font-size:11px;color:#334155;line-height:1.8'>"
        "<div style='color:#ef4444'>● FLAGGED</div>Score ≥ 60 — block<br>"
        "<div style='color:#f59e0b'>● REVIEW</div>Score 30–59 — investigate<br>"
        "<div style='color:#22c55e'>● CLEAN</div>Score 0–29 — allow</div>",
        unsafe_allow_html=True,
    )

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""<div class="control-header"><div class="header-dot"></div>
<div><div class="header-title">AML Auditor — Live Control Room</div>
<div class="header-sub">Multi-Agent Anti-Money Laundering Detection System</div></div></div>""",
unsafe_allow_html=True)

# ── Fetch data ─────────────────────────────────────────────────────────────────
results = get("/results").get("results", [])

if results:
    seen = {v.get("transaction_id") for v in st.session_state.verdicts}
    for r in reversed(results):
        if r.get("transaction_id") not in seen:
            st.session_state.verdicts.appendleft(r)
            st.session_state.total += 1
            vv = str(r.get("final_verdict", r.get("status", ""))).upper()
            if vv == "FLAGGED":  st.session_state.flagged += 1
            elif vv == "REVIEW": st.session_state.review  += 1
            st.session_state.scores.append(r.get("final_risk_score", r.get("risk_score", 0)))

# ── Metrics ────────────────────────────────────────────────────────────────────
avg = round(sum(st.session_state.scores) / len(st.session_state.scores)) if st.session_state.scores else 0
st.markdown(f"""<div class="metric-row">
  <div class="metric-card"><div class="metric-label">Total Transactions</div><div class="metric-value blue">{st.session_state.total}</div></div>
  <div class="metric-card"><div class="metric-label">Flagged</div><div class="metric-value red">{st.session_state.flagged}</div></div>
  <div class="metric-card"><div class="metric-label">Under Review</div><div class="metric-value amber">{st.session_state.review}</div></div>
  <div class="metric-card"><div class="metric-label">Avg Risk Score</div><div class="metric-value" style="color:{score_color(avg)}">{avg}</div></div>
</div>""", unsafe_allow_html=True)

st.markdown("<hr style='border:none;border-top:1px solid #1e2a3a;margin:20px 0'>", unsafe_allow_html=True)

# ── Feed + Analysis ────────────────────────────────────────────────────────────
all_v = list(st.session_state.verdicts)
if filter_verdict != "All":
    all_v = [v for v in all_v if str(v.get("final_verdict", v.get("status", ""))).upper() == filter_verdict]

col1, col2 = st.columns([1, 1], gap="medium")
with col1:
    st.markdown("<div class='section-title'>📡 Live Transaction Feed</div>", unsafe_allow_html=True)
    feed = '<div class="feed-scroll">'
    for v in all_v[:25]:
        feed += txn_html(v)
    if not all_v:
        feed += "<div style='color:#475569;font-size:12px;padding:20px;text-align:center'>Waiting for transactions…<br><small>Make sure backend + simulator are running</small></div>"
    feed += "</div>"
    st.markdown(feed, unsafe_allow_html=True)

with col2:
    st.markdown("<div class='section-title'>🎯 Latest Transaction Analysis</div>", unsafe_allow_html=True)
    latest = list(st.session_state.verdicts)[0] if st.session_state.verdicts else None
    if latest:
        score = latest.get("final_risk_score", latest.get("risk_score", 0))
        sc    = score_color(score)
        st.markdown(
            f"<div style='text-align:center;margin-bottom:4px'>"
            f"<span style='font-size:13px;font-weight:700;font-family:JetBrains Mono,monospace;color:#94a3b8'>"
            f"{latest.get('transaction_id','')}</span></div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(make_gauge(score), use_container_width=True, key=f"g_{latest.get('transaction_id','')}")
        ca, cb = st.columns(2)
        with ca:
            st.markdown(
                f"<div style='text-align:center'><div style='font-size:10px;color:#475569;margin-bottom:2px'>USER</div>"
                f"<div style='font-size:13px;color:#60a5fa;font-weight:700;font-family:JetBrains Mono,monospace'>"
                f"{latest.get('user_id','?')}</div></div>",
                unsafe_allow_html=True,
            )
        with cb:
            st.markdown(
                f"<div style='text-align:center'><div style='font-size:10px;color:#475569;margin-bottom:2px'>AMOUNT</div>"
                f"<div style='font-size:13px;color:{sc};font-weight:700;font-family:JetBrains Mono,monospace'>"
                f"${latest.get('amount_usd',0):,.2f}</div></div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div style='margin-top:10px'>"
            f"<div style='font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px'>Agent Flags</div>"
            f"{agents_html(latest)}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='margin-top:12px'>"
            f"<div style='font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px'>AI Debate</div>"
            f"{debate_html(latest)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#475569;font-size:12px;padding:20px;text-align:center'>Waiting for first transaction…</div>",
            unsafe_allow_html=True,
        )

# ── Timeline ───────────────────────────────────────────────────────────────────
st.markdown("<div style='margin-top:16px'><div class='section-title'>📈 Risk Score Timeline</div></div>", unsafe_allow_html=True)
st.plotly_chart(make_timeline(list(st.session_state.scores)), use_container_width=True, key="timeline")

# ── Fraud ring graph ───────────────────────────────────────────────────────────
st.markdown("<div class='section-title' style='margin-top:16px'>🕸 Transaction Network — Fraud Ring Detection</div>", unsafe_allow_html=True)
gdata = get("/fraud_graph", timeout=5)
if gdata:
    gd    = gdata.get("graph_data", {})
    nodes = gd.get("nodes", [])
    rings = gd.get("rings", [])
    html  = gdata.get("html", "")
    if nodes:
        st.markdown(
            f"<div style='font-size:12px;color:#94a3b8;margin-bottom:8px'>"
            f"<span style='color:#ef4444;font-weight:700'>{len(nodes)}</span> flagged users in graph</div>",
            unsafe_allow_html=True,
        )
        if rings:
            st.markdown(
                f"<div style='background:#1a0a0a;border:1px solid #7f1d1d;border-radius:8px;padding:10px 14px;"
                f"margin-bottom:8px;font-size:12px'>"
                f"<span style='color:#ef4444;font-weight:700'>🔴 {len(rings)} money ring(s) detected</span>"
                f"<span style='color:#94a3b8;margin-left:8px'>{' | '.join([' → '.join(r) for r in rings[:3]])}</span></div>",
                unsafe_allow_html=True,
            )
        if html:
            st.components.v1.html(html, height=420, scrolling=False)
    else:
        st.markdown(
            "<div style='color:#475569;font-size:12px;padding:16px;text-align:center;"
            "background:#0d1117;border:1px solid #1e2a3a;border-radius:8px'>"
            "No flagged users yet — graph appears as transactions are flagged</div>",
            unsafe_allow_html=True,
        )

# ── Auto refresh ───────────────────────────────────────────────────────────────
time.sleep(refresh_rate)
st.rerun()