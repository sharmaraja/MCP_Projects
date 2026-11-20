import asyncio
from pathlib import Path

import streamlit as st
from mcp_client import (
    get_mcp_capabilities,
    read_resource_content,
    render_mcp_prompt,
    run_mcp_agent_turn,
)

st.set_page_config(page_title="Personal Finance MCP Host", page_icon="💳", layout="wide")

st.title("💳 Personal Finance & UPI Analytics — MCP Host")
st.caption("Powered by Official MCP Python SDK v2 (`stdio`), SQLite, and Llama 3.3")

DB_PATH = Path(__file__).resolve().parent.parent / "finance.db"
if not DB_PATH.exists():
    st.error("Database `finance.db` not found! Run `python code_base/seed.py` from the project root first.")
    st.stop()

# Cache MCP server discovery metadata
@st.cache_data(ttl=60)
def load_capabilities():
    return asyncio.run(get_mcp_capabilities())

caps = load_capabilities()

# Sidebar: Live MCP Primitives Inspector
with st.sidebar:
    st.header("🔌 Live MCP Server Inspector")

    with st.expander(f"🛠️ MCP Tools ({len(caps['tools'])})", expanded=True):
        for tool in caps["tools"]:
            badge = "🟢 Read-Only" if tool["read_only"] else "🟠 Write / Mutating"
            st.markdown(f"**`{tool['name']}`** ({badge})")
            st.caption(tool["description"])

    with st.expander("📂 MCP Resources", expanded=True):
        for res in caps["resources"]:
            st.markdown(f"- `{res['uri']}`")
        for tmpl in caps["resource_templates"]:
            st.markdown(f"- `{tmpl['uriTemplate']}`")

        selected_month = st.selectbox("Inspect Monthly Resource", ["2026-09", "2026-10", "2026-11"], index=1)
        if st.button("Read `finance://summary` Resource"):
            resource_text = asyncio.run(read_resource_content(f"finance://summary/{selected_month}"))
            st.info(resource_text)

    with st.expander("⚡ MCP Prompts (Workflows)", expanded=True):
        audit_month = st.selectbox("Audit Month", ["2026-09", "2026-10", "2026-11"], index=1, key="audit_m")
        savings_goal = st.number_input("Savings Target (₹)", min_value=5000, max_value=200000, value=50000, step=5000)
        if st.button("Run `monthly_budget_audit` Prompt"):
            prompt_text = asyncio.run(
                render_mcp_prompt("monthly_budget_audit", {"month": audit_month, "savings_target_inr": str(savings_goal)})
            )
            st.session_state.pending_prompt = prompt_text

    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.rerun()

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render Existing Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("traces"):
            with st.expander("🔍 View MCP Tool Execution Trace"):
                for idx, tr in enumerate(msg["traces"], 1):
                    st.markdown(f"**Step {idx}: Called MCP Tool `{tr['tool']}`**")
                    st.json(tr["args"])
                    st.code(tr["output"], language="text")

# Handle either typed input or triggered MCP Prompt button
user_input = st.chat_input("Ask about UPI spending, subscriptions, or log a new expense...")
if "pending_prompt" in st.session_state:
    user_input = st.session_state.pop("pending_prompt")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Executing MCP tools over stdio..."):
            reply, traces = asyncio.run(run_mcp_agent_turn(st.session_state.messages[:-1], user_input))
            st.markdown(reply)

            if traces:
                with st.expander("🔍 View MCP Tool Execution Trace"):
                    for idx, tr in enumerate(traces, 1):
                        st.markdown(f"**Step {idx}: Called MCP Tool `{tr['tool']}`**")
                        st.json(tr["args"])
                        st.code(tr["output"], language="text")

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply,
        "traces": traces,
    })