# 🛡️ FinGuard-AI

### AI-Powered Multi-Agent Anti-Money Laundering Investigation Platform

FinGuard-AI is an intelligent Anti-Money Laundering (AML) platform that combines traditional fraud detection techniques with Generative AI-powered investigation agents.

The system continuously monitors banking transactions, identifies suspicious activities, launches a multi-agent investigation workflow, and visualizes transaction networks through an interactive dashboard.

---

## 🚀 Problem Statement

Financial institutions process millions of transactions daily.

Traditional rule-based systems generate thousands of alerts, forcing analysts to manually investigate each case. This process is expensive, time-consuming, and often leads to false positives.

FinGuard-AI addresses this challenge by:

* Detecting suspicious transactions automatically
* Assigning risk scores based on multiple fraud indicators
* Launching AI-powered investigations
* Providing explainable verdicts
* Visualizing hidden transaction networks
* Delivering real-time monitoring through an interactive dashboard

---

# 🏗️ System Architecture

```text
                         ┌────────────────────┐
                         │ Transaction        │
                         │ Simulator          │
                         └─────────┬──────────┘
                                   │
                                   ▼
                     ┌──────────────────────────┐
                     │ FastAPI Backend          │
                     │ Transaction Ingestion    │
                     └─────────┬────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼

 ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
 │ Geo Velocity   │  │ Structuring    │  │ Behavioral     │
 │ Detection      │  │ Detection      │  │ Analysis       │
 └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼

                 ┌────────────────────────┐
                 │ Risk Scoring Engine    │
                 └──────────┬─────────────┘
                            │
             Risk Score > Threshold?
                            │
               ┌────────────┴────────────┐
               │                         │
               ▼                         ▼

      Low Risk Transaction      High Risk Transaction
           Stored                    Investigation
                                       Triggered
                                           │
                                           ▼

                          ┌─────────────────────────┐
                          │ LangGraph Workflow      │
                          └──────────┬──────────────┘
                                     │
        ┌────────────────────────────┼──────────────────────────┐
        │                            │                          │
        ▼                            ▼                          ▼

 ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
 │ Prosecutor AI  │      │ Defense AI     │      │ Supervisor AI  │
 │ Agent          │      │ Agent          │      │ Agent          │
 └───────┬────────┘      └───────┬────────┘      └───────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼

                       ┌──────────────────┐
                       │ Judge AI Agent   │
                       └────────┬─────────┘
                                │
                                ▼

                     ┌──────────────────────┐
                     │ Final Verdict        │
                     │ Fraud / Legitimate   │
                     └─────────┬────────────┘
                               │
                               ▼

             ┌──────────────────────────────────┐
             │ Transaction Network Analysis     │
             │ Fraud Ring Visualization         │
             └───────────────┬──────────────────┘
                             │
                             ▼

                ┌──────────────────────────┐
                │ Streamlit Dashboard      │
                │ Live Monitoring          │
                │ Agent Reasoning          │
                │ Graph Visualization      │
                └──────────────────────────┘
```

---

# 🔍 Core Features

## 1. Transaction Simulator

A synthetic banking environment that continuously generates realistic financial transactions.

Features:

* Real-time transaction generation
* Normal and suspicious transactions
* Repeatable fraud scenarios
* Ideal for demonstrations and testing

---

## 2. Geo-Velocity Detection

Detects physically impossible travel patterns.

Example:

```text
London → Mumbai
10 Minutes Apart
```

The system calculates the required travel speed.

If impossible, the transaction is flagged.

---

## 3. Structuring Detection

Identifies attempts to bypass regulatory reporting limits.

Example:

```text
$9,900
$9,800
$9,950
```

instead of:

```text
$10,000
```

Common money laundering tactic.

---

## 4. Behavioral Analysis

Builds spending profiles for users.

Detects:

* Unusual spending
* Abnormal transaction frequency
* Unexpected transfer amounts

---

## 5. Risk Scoring Engine

Every transaction receives a score between:

```text
0 - 100
```

Example:

| Indicator          | Score |
| ------------------ | ----- |
| Geo Velocity       | +40   |
| Structuring        | +35   |
| Behavioral Anomaly | +25   |

Final Score:

```text
100/100
```

---

## 6. Multi-Agent Investigation

High-risk transactions trigger a collaborative AI investigation.

### Prosecutor Agent

Argues why the transaction is suspicious.

### Defense Agent

Provides alternative legitimate explanations.

### Judge Agent

Evaluates both sides and issues the final verdict.

### Supervisor Agent

Coordinates investigation flow and agent communication.

---

## 7. Transaction Network Analysis

Builds relationship graphs between accounts.

Helps uncover:

* Fraud rings
* Layering activities
* Suspicious account clusters
* Hidden transaction paths

---

## 8. Real-Time Dashboard

Interactive Streamlit dashboard providing:

* Live transaction feed
* Risk monitoring
* AI investigation logs
* Verdict tracking
* Transaction graph visualization

---

# 🧠 Tech Stack

### Backend

* FastAPI
* Python

### AI & Agents

* LangGraph
* Groq LLM

### Frontend

* Streamlit

### Graph Analytics

* NetworkX

### Data Storage

* SQLite
* PostgreSQL (Planned)

### Real-Time Communication

* WebSockets

---

# 📂 Project Structure

```text
FinGuard-AI
│
├── backend
│   ├── agents
│   │   ├── prosecution.py
│   │   ├── defense.py
│   │   ├── judge.py
│   │   ├── supervisor.py
│   │   ├── behavioral.py
│   │   ├── geo_velocity.py
│   │   └── structuring.py
│   │
│   ├── graph
│   │   └── aml_graph.py
│   │
│   ├── network
│   │   └── tx_graph.py
│   │
│   ├── database.py
│   ├── risk_score.py
│   └── main.py
│
├── dashboard
│   └── dashboard.py
│
├── simulator
│   └── simulator.py
│
├── requirements.txt
└── README.md
```

---

# ▶️ Running the Project

### Start Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### Start Transaction Simulator

```bash
python simulator/simulator.py
```

### Launch Dashboard

```bash
streamlit run dashboard/dashboard.py
```

---

# 🎯 Future Enhancements

* PostgreSQL Integration
* IBM Cloud Deployment
* Docker Containerization
* Cloud Object Storage
* PDF Investigation Reports
* User Authentication
* Human-in-the-Loop Review System
* Advanced Fraud Ring Detection

---

# 👨‍💻 Author

**Sahil Desai**

B.Tech EXTC, VJTI Mumbai

AI • Machine Learning • Multi-Agent Systems • Data Science
