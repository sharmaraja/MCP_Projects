# 💳 Personal Finance & UPI Analytics MCP Server

An end-to-end **Model Context Protocol (MCP)** server and custom **MCP Host** built with the official MCP Python SDK v2 (`MCPServer`). It enables AI agents and desktop clients (Claude Desktop, Cursor, or the bundled Streamlit Host) to safely query, audit, and update a local SQLite personal finance ledger using standardized MCP **Tools**, **Resources**, and **Prompts**.

## 🎯 Why MCP for This Use Case?

Giving an LLM raw database credentials creates severe SQL injection and accidental deletion risks, while hardcoding database queries inside a UI locks business logic away from other AI agents. Implementing this as an MCP Server solves both problems:

* **Protocol Standardization:** Any MCP-compatible client can discover schemas, read summaries, and execute tools over `stdio` without custom glue code.
* **Granular Capability Control:** Read-only analytics tools (`read_only_hint=True`) are explicitly separated from state-mutating write tools (`log_transaction`), and SQL queries pass through a strict `SELECT`-only guard.

## 🏗️ Architecture

```text
┌──────────────────────────────────────────────────────────┐
│               MCP Host (Streamlit UI / Claude)           │
│  ┌────────────────┐  ┌────────────────────────────────┐  │
│  │ LLM (Llama 3.3)│◄─┤ MCP ClientSession (stdio JSON) │  │
│  └────────────────┘  └───────────────┬────────────────┘  │
└──────────────────────────────────────┼───────────────────┘
                                       │ JSON-RPC over stdio
┌──────────────────────────────────────▼───────────────────┐
│             Personal Finance MCP Server                  │
│  ├── Resources: finance://schema, finance://summary/{m}  │
│  ├── Tools:     run_readonly_sql, get_category_breakdown │
│  │              detect_recurring_subscriptions           │
│  │              log_transaction (write-annotated)        │
│  └── Prompts:   monthly_budget_audit                     │
└──────────────────────────────────────┬───────────────────┘
                                       ▼
                              [SQLite: finance.db]
```

## 🧩 Implemented MCP Primitives

| Primitive | Name / URI | Control Model | Purpose |
| :--- | :--- | :--- | :--- |
| **Resource** | `finance://schema` | Application | Injects SQLite DDL schema & valid categories into model context. |
| **Resource** | `finance://summary/{month}` | Application | Dynamic URI template returning monthly income, debits, and net cash flow. |
| **Tool** | `run_readonly_sql` | Model (`read_only`) | Executes guarded `SELECT` queries for custom financial slicing. |
| **Tool** | `get_category_breakdown` | Model (`read_only`) | Deterministic aggregation by category and payment mode (UPI/Card/NEFT). |
| **Tool** | `detect_recurring_subscriptions` | Model (`read_only`) | Identifies fixed-amount recurring debits across months. |
| **Tool** | `log_transaction` | Model (`write`) | Pydantic-validated insertion of new income or expense entries. |
| **Prompt** | `monthly_budget_audit` | User | Multi-step audit template comparing net savings against a target in INR. |

## 🚀 Quickstart

Run these commands from the project root.

1. **Install Dependencies**
   ```bash
   python -m pip install -r requirements.txt
   ```

2. **Set Up Environment**
   Add your Groq API key to `.env`:
   ```env
   GROQ_API_KEY=your_groq_api_key
   ```

3. **Seed the SQLite Ledger** (only if `finance.db` does not already exist)
   ```bash
   python code_base/seed.py
   ```

4. **Launch the Streamlit MCP Host**
   ```bash
   streamlit run code_base/app.py
   ```

## 🖥️ Connecting to Claude Desktop (Optional)

Because `mcp_server.py` speaks standard MCP over `stdio`, you can plug it directly into Claude Desktop by adding this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "personal-finance": {
      "command": "python",
      "args": ["C:/absolute/path/to/Financial_Analysis_Agent/code_base/mcp_server.py"]
    }
  }
}
```