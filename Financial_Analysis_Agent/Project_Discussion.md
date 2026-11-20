# 💳 Personal Finance & UPI Analytics MCP Server

An end-to-end **Model Context Protocol (MCP)** server and custom **MCP Host** built with the official MCP Python SDK v2 (`MCPServer`). It enables AI agents and desktop clients (such as Claude Desktop, Cursor, or the bundled Streamlit Host) to safely query, audit, and update a local SQLite personal finance ledger using standardized MCP **Tools**, **Resources**, and **Prompts**.

---

## 🎯 Why MCP for This Use Case?

Giving an LLM raw database credentials creates severe SQL injection and accidental deletion risks, while hardcoding database queries inside a UI locks business logic away from other AI agents. Implementing this system as an **MCP Server** solves both problems:

* **Protocol Standardization:** Any MCP-compatible client can discover schemas, read financial summaries, and execute tools over `stdio` without custom integration glue code.
* **Granular Capability Control:** Read-only analytics tools (`read_only_hint=True`) are explicitly separated from state-mutating write tools (`log_transaction`), and custom SQL queries pass through a strict `SELECT`-only guardrail.

---

## 📁 Project Structure & What Every File Does

```text
mcp-finance-server/
├── finance.db             # Auto-generated SQLite 3 relational database
├── .env                   # Environment configuration storing GROQ_API_KEY
├── requirements.txt       # Python package dependencies
├── seed_db.py             # Database initializer, synthetic generator & CSV ETL pipeline
├── mcp_server.py          # Core MCP Server exposing Tools, Resources & Prompts over stdio
├── mcp_client.py          # MCP Host/Client bridge & Groq LLM tool-calling orchestrator
├── app.py                 # Streamlit web UI for interacting with & inspecting the MCP Server
└── README.md              # Complete architectural and setup documentation
```

### Detailed File Breakdown
1. **`seed_db.py` (Data Ingestion & ETL Layer):**
   * Creates the `finance.db` SQLite database and enforces the `transactions` table schema (`id`, `txn_date`, `merchant`, `category`, `payment_mode`, `txn_type`, `amount_inr`, `notes`).
   * Populates the database either by generating realistic Indian UPI/bank transactions or by cleaning and normalizing external CSV datasets.
2. **`finance.db` (Storage Layer):**
   * A self-contained, single-file **SQLite 3 binary relational database**. It acts as the persistent source of truth for all debit/credit records without requiring an external database server.
3. **`mcp_server.py` (MCP Protocol Server):**
   * The core backend built with `MCPServer`. It runs as an isolated subprocess communicating via JSON-RPC over standard input/output (`stdio`).
   * Exposes **Resources** (schema and monthly cash-flow snapshots), **Tools** (guarded SQL execution, category breakdowns, recurring subscription detection, and validated transaction logging), and **Prompts** (structured budget audit templates).
4. **`mcp_client.py` (MCP Client & Agent Orchestrator):**
   * Acts as the programmatic bridge between the user interface, the LLM, and the MCP server.
   * Spawns `mcp_server.py` via `StdioServerParameters`, dynamically fetches available tools/resources, translates MCP JSON schemas into Groq function-calling definitions, and executes multi-step tool-calling loops.
5. **`app.py` (Streamlit MCP Host UI):**
   * Provides a visual web interface for users and developers.
   * Features a live **MCP Server Inspector** sidebar (displaying read/write tool badges, resource readers, and one-click prompt triggers) alongside a conversational chat interface with expandable JSON execution traces.
6. **`requirements.txt` & `.env` (Configuration):**
   * `requirements.txt` pins the official MCP SDK, Streamlit, Groq client, Pandas, and Pydantic. `.env` securely stores your `GROQ_API_KEY` outside version control.

---

## 📊 Where the Data Comes From

The pipeline is designed to support **two data ingestion modes** inside `seed_db.py`:

1. **Out-of-the-Box Synthetic Indian UPI/Bank Generator (Default):**
   * When `init_and_seed_db()` is run without arguments, it generates 3 months of realistic Indian personal finance records (monthly salary credits via NEFT, house rent via UPI, recurring UPI AutoPay/Credit Card subscriptions like Airtel Fiber, Netflix, and Spotify, plus randomized daily spends across Swiggy, Zomato, Blinkit, Uber, IRCTC, and Amazon).
   * This guarantees zero-friction reproducibility for anyone cloning the repository.
2. **External Real-World Datasets (Kaggle & GitHub CSVs):**
   * You can plug in real transaction CSVs such as the [Kaggle UPI Apps Transaction Dataset](https://www.kaggle.com/code/manishabulbule/upi-apps-transaction) or the [GitHub Bank Transaction Analytics Dataset](https://github.com/prachi-singh-ds/Bank-Transaction-Analytics-Dashboard).
   * Because public CSVs use inconsistent headers (e.g., `Date`, `Transaction_Type`, `Amount`), `seed_db.py` includes a Pandas ETL normalization function that maps columns, standardizes dates to `YYYY-MM-DD`, converts types to `DEBIT`/`CREDIT`, and appends clean records into `finance.db`.

---

## 🔄 End-to-End Execution Flow (Input to Output)

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 1. USER INPUT (Streamlit UI: Chat Query or One-Click MCP Prompt)     │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 2. MCP CLIENT SESSION (mcp_client.py)                                │
│    • Spawns `mcp_server.py` subprocess via stdio                     │
│    • Reads `finance://schema` Resource for table & category context  │
│    • Fetches MCP Tools & converts inputSchemas for Groq LLM          │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 3. LLM REASONING & TOOL SELECTION (Llama-3.3-70B @ Temp 0.0)         │
│    • Analyzes user intent + database schema                          │
│    • Emits structured tool call(s) (e.g., `get_category_breakdown`)  │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 4. MCP SERVER EXECUTION & GUARDRAILS (mcp_server.py)                 │
│    • Receives JSON-RPC `call_tool` request over stdin                │
│    • Validates inputs via Pydantic & blocks non-SELECT SQL writes    │
│    • Queries `finance.db` (SQLite) and returns formatted result      │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 5. FINAL SYNTHESIS & UI RENDERING (app.py)                           │
│    • LLM synthesizes exact INR figures into a clear answer           │
│    • Streamlit displays response + expandable JSON tool trace        │
└──────────────────────────────────────────────────────────────────────┘
```

### Step-by-Step Walkthrough
1. **Input Capture:** The user either types a natural-language question in `app.py` (e.g., *"How much did I spend on Food & Dining via UPI in October 2026?"*) or clicks **Run `monthly_budget_audit` Prompt** in the sidebar.
2. **Session Initialization & Context Grounding:** `mcp_client.py` launches `mcp_server.py` over `stdio`, completes the MCP handshake (`session.initialize()`), and automatically reads the `finance://schema` **MCP Resource**. This injects exact SQL column names, valid categories, and available months into the LLM's system prompt so it never hallucinates column names.
3. **Tool Discovery & LLM Routing:** `mcp_client.py` calls `session.list_tools()` and passes the tool definitions to **Llama 3.3 70B**. The model determines which MCP tool(s) to invoke and constructs valid JSON arguments.
4. **Protocol Execution & Database Querying:** `mcp_client.py` sends a `session.call_tool()` JSON-RPC message to `mcp_server.py`. The server validates parameters using **Pydantic**, enforces read-only SQL regex checks (if `run_readonly_sql` is called), executes the query against `finance.db`, and writes execution logs to `stderr` (keeping `stdout` strictly clean for JSON-RPC).
5. **Iterative Loop & Output Rendering:** The tool output is fed back to the LLM. If multi-step reasoning is needed (e.g., checking subscriptions after checking category totals), the LLM can chain up to 5 tool calls before generating the final answer in `₹` (INR). `app.py` renders the final answer along with an expandable **MCP Tool Execution Trace** showing every tool name, JSON argument payload, and raw database output.

---

## 🧠 LLM & Tech Stack Overview

| Component | Technology | Role & Architectural Justification |
| :--- | :--- | :--- |
| **LLM Engine** | **Llama-3.3-70b-versatile** *(via Groq API)* | A 70-billion-parameter open-weights model capable of reliable SQL generation and multi-step tool calling. Configured at `temperature=0.0` for deterministic argument extraction, hosted on Groq's LPU inference engine for near-instant responses on the free tier. |
| **Agent Protocol** | **MCP Python SDK v2** (`mcp[cli] >= 2.0.0`) | Implements the open Model Context Protocol standard using `MCPServer`, `ClientSession`, `stdio` transport, and `ToolAnnotations` (`read_only_hint`). |
| **Database** | **SQLite 3** (`sqlite3`) | Zero-configuration, embedded relational SQL database storing `finance.db` locally with ACID compliance and `CHECK` constraints. |
| **Frontend / Host** | **Streamlit** (`>= 1.40.0`) | Rapidly delivers an interactive MCP Host UI with session-persisted chat history, live primitive inspection, and JSON trace drawers. |
| **Data & Validation** | **Pydantic v2 & Pandas** | Pydantic enforces strict runtime schema validation and JSON schema generation for all MCP tool inputs; Pandas handles CSV ETL normalization. |

---

## 🧩 Implemented MCP Primitives Reference

| Primitive | Name / URI | Control Model | Purpose |
| :--- | :--- | :--- | :--- |
| **Resource** | `finance://schema` | Application | Injects SQLite DDL schema, valid categories, and months into model context. |
| **Resource** | `finance://summary/{month}` | Application | Dynamic URI template returning monthly income, debits, and net cash flow. |
| **Tool** | `run_readonly_sql` | Model (`read_only`) | Executes guarded `SELECT` queries for custom financial slicing. |
| **Tool** | `get_category_breakdown` | Model (`read_only`) | Deterministic aggregation by category and payment mode (UPI/Card/NEFT). |
| **Tool** | `detect_recurring_subscriptions` | Model (`read_only`) | Identifies fixed-amount recurring debits across multiple months. |
| **Tool** | `log_transaction` | Model (`write`) | Pydantic-validated insertion of new income or expense entries. |
| **Prompt** | `monthly_budget_audit` | User | Multi-step audit template comparing net savings against a target in INR. |

---

## 🚀 Quickstart

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   Create a `.env` file in the root directory and add your free API key from [Groq Console](https://console.groq.com/):
   ```env
   GROQ_API_KEY=gsk_your_api_key_here
   ```

3. **Seed the SQLite Ledger**
   ```bash
   python seed_db.py
   ```

4. **Launch the Streamlit MCP Host**
   ```bash
   streamlit run app.py
   ```

5. *(Optional)* **Connect to Claude Desktop**
   Because `mcp_server.py` speaks standard MCP over `stdio`, you can register it directly in `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "personal-finance": {
         "command": "python",
         "args": ["/absolute/path/to/mcp-finance-server/mcp_server.py"]
       }
     }
   }
   ```