
import logging
import re
import sqlite3
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

# Configure logging to stderr (CRITICAL for stdio transport)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finance-mcp-server")

DB_PATH = Path(__file__).resolve().parent.parent / "finance.db"
mcp = MCPServer("Personal-Finance-UPI-Server")

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =====================================================================
# 1. MCP RESOURCES (Application-Controlled Context)
# =====================================================================

@mcp.resource("finance://schema")
def get_database_schema() -> str:
    """Returns the SQLite database schema and valid categories for query grounding."""
    conn = get_db_connection()
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone()
    categories = [
        r["category"]
        for r in conn.execute("SELECT DISTINCT category FROM transactions").fetchall()
    ]
    months = [
        r["m"]
        for r in conn.execute(
            "SELECT DISTINCT substr(txn_date, 1, 7) AS m FROM transactions ORDER BY m"
        ).fetchall()
    ]
    conn.close()

    schema_sql = schema_row["sql"] if schema_row else "Table not found."
    return (
        f"SQLite Schema:\n{schema_sql}\n\n"
        f"Available Categories: {', '.join(categories)}\n"
        f"Available Months (YYYY-MM): {', '.join(months)}"
    )

@mcp.resource("finance://summary/{month}")
def get_monthly_summary_resource(month: str) -> str:
    """Dynamic resource returning total credits, debits, and net savings for YYYY-MM."""
    if not re.match(r"^\d{4}-\d{2}$", month):
        return "Invalid format. Use YYYY-MM (e.g., 2026-10)."

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT txn_type, ROUND(SUM(amount_inr), 2) AS total, COUNT(*) AS count
        FROM transactions
        WHERE substr(txn_date, 1, 7) = ?
        GROUP BY txn_type
        """,
        (month,),
    ).fetchall()
    conn.close()

    if not rows:
        return f"No transactions found for {month}."

    summary = {r["txn_type"]: (r["total"], r["count"]) for r in rows}
    credits, c_cnt = summary.get("CREDIT", (0.0, 0))
    debits, d_cnt = summary.get("DEBIT", (0.0, 0))
    net = round(credits - debits, 2)

    return (
        f"Financial Snapshot for {month}:\n"
        f"- Total Income (CREDIT): ₹{credits:,.2f} ({c_cnt} txns)\n"
        f"- Total Expenses (DEBIT): ₹{debits:,.2f} ({d_cnt} txns)\n"
        f"- Net Cash Flow: ₹{net:,.2f}"
    )

# =====================================================================
# 2. MCP TOOLS (Model-Controlled Actions with Safety Annotations)
# =====================================================================

@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
async def run_readonly_sql(
    query: Annotated[str, Field(description="A valid SQLite SELECT query against the 'transactions' table.")],
) -> str:
    """Execute a safe, read-only SQL SELECT query to analyze spending, merchants, or payment modes."""
    cleaned = query.strip().rstrip(";")
    if not cleaned.upper().startswith("SELECT"):
        return "Security Error: Only SELECT queries are permitted."

    forbidden = r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|PRAGMA|ATTACH)\b"
    if re.search(forbidden, cleaned, re.IGNORECASE):
        return "Security Error: Mutating or administrative SQL keywords are blocked."

    logger.info("Executing read-only SQL: %s", cleaned)
    try:
        conn = get_db_connection()
        cursor = conn.execute(cleaned)
        rows = [dict(row) for row in cursor.fetchmany(50)]
        conn.close()

        if not rows:
            return "Query executed successfully but returned 0 rows."
        return str(rows)
    except sqlite3.Error as e:
        return f"SQLite Error: {str(e)}"

@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def get_category_breakdown(
    month: Annotated[str, Field(description="Month in YYYY-MM format, e.g. '2026-10'")],
) -> str:
    """Get total debit spending grouped by category and payment mode for a given month."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT category, payment_mode, COUNT(*) AS txns, ROUND(SUM(amount_inr), 2) AS total_inr
        FROM transactions
        WHERE txn_type = 'DEBIT' AND substr(txn_date, 1, 7) = ?
        GROUP BY category, payment_mode
        ORDER BY total_inr DESC
        """,
        (month,),
    ).fetchall()
    conn.close()

    if not rows:
        return f"No debit transactions found for {month}."

    lines = [f"Category Breakdown for {month}:"]
    for r in rows:
        lines.append(f"- {r['category']} ({r['payment_mode']}): ₹{r['total_inr']:,.2f} across {r['txns']} txns")
    return "\n".join(lines)

@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def detect_recurring_subscriptions() -> str:
    """Identify recurring monthly subscriptions or repeated fixed-amount merchant charges."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT merchant, category, payment_mode, amount_inr, COUNT(DISTINCT substr(txn_date, 1, 7)) AS months_charged
        FROM transactions
        WHERE txn_type = 'DEBIT'
        GROUP BY merchant, amount_inr
        HAVING months_charged >= 2
        ORDER BY amount_inr DESC
        """
    ).fetchall()
    conn.close()

    if not rows:
        return "No recurring fixed-amount charges detected."

    lines = ["Detected Recurring Charges:"]
    for r in rows:
        lines.append(
            f"- {r['merchant']} ({r['payment_mode']}): ₹{r['amount_inr']:,.2f}/month "
            f"(seen across {r['months_charged']} months)"
        )
    return "\n".join(lines)

@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False))
async def log_transaction(
    txn_date: Annotated[str, Field(description="Date in YYYY-MM-DD format")],
    merchant: Annotated[str, Field(description="Merchant or payee name, e.g., 'Swiggy'")],
    category: Annotated[str, Field(description="Category, e.g., 'Food & Dining', 'Transport', 'Groceries'")],
    payment_mode: Annotated[Literal["UPI", "Credit Card", "NetBanking", "UPI AutoPay", "Cash"], Field(description="Mode of payment")],
    txn_type: Annotated[Literal["DEBIT", "CREDIT"], Field(description="DEBIT for expense, CREDIT for income")],
    amount_inr: Annotated[float, Field(gt=0, description="Transaction amount in INR")],
    notes: Annotated[str, Field(description="Optional short description")] = "",
) -> str:
    """Insert a new financial transaction into the SQLite ledger."""
    logger.info("Logging new %s of %.2f at %s", txn_type, amount_inr, merchant)
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO transactions (txn_date, merchant, category, payment_mode, txn_type, amount_inr, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (txn_date, merchant, category, payment_mode, txn_type, amount_inr, notes),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return f"Successfully logged transaction #{new_id}: {txn_type} of ₹{amount_inr:,.2f} for {merchant} on {txn_date}."

# =====================================================================
# 3. MCP PROMPTS (User-Controlled Structured Workflows)
# =====================================================================

@mcp.prompt()
def monthly_budget_audit(month: str = "2026-10", savings_target_inr: float = 50000.0) -> str:
    """Generate a structured personal finance audit workflow for a specific month."""
    return (
        f"Perform a comprehensive personal finance audit for {month}.\n"
        f"1. Call `get_category_breakdown` for '{month}' and `detect_recurring_subscriptions`.\n"
        f"2. Calculate total income vs. total expenses for {month} using `run_readonly_sql`.\n"
        f"3. Compare net savings against my target of ₹{savings_target_inr:,.2f}.\n"
        f"4. Highlight top 3 discretionary spending categories (especially UPI impulse spends) "
        f"and give 3 concrete, actionable recommendations in INR."
    )

if __name__ == "__main__":
    mcp.run(transport="stdio")