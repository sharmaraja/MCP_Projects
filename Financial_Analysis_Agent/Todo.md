Must-Do Upgrades (Core Engineering)
Pydantic Structured Outputs: Return typed Pydantic models instead of plain text so the LLM parses currency figures without formatting errors.

MCP Elicitation (Human-in-the-Loop): Pause write tools like log_transaction to request explicit user confirmation before modifying SQLite.

Streamable HTTP Transport: Switch from local stdio to streamable-http so your server can be deployed to the cloud and accessed over HTTP.

Inspector & Automated Tests: Debug raw JSON-RPC payloads with mcp dev mcp_server.py and write pytest checks to verify SQL injection blocks.

Can-Do Experiments (Advanced MCP Variations)
Multi-Server Host: Connect mcp_client.py to two servers simultaneously (e.g., your Finance MCP + a Filesystem MCP to export Markdown audit reports).

Async Tasks & Progress: Use the MCP Tasks extension with ctx.report_progress() to process large bank CSV uploads asynchronously.

Resource Caching & Links: Add ttlMs caching to finance://schema and return clickable finance://summary/{month} links from tool outputs.

OAuth 2.1 & Tracing: Secure your HTTP endpoint with OAuth 2.1 bearer tokens and trace calls using OpenTelemetry headers.

MCP Apps: Experiment with returning interactive charts or forms directly from the server into supporting chat clients.