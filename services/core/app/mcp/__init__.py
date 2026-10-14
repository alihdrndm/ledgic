"""Ledgic MCP server: AP tools for Claude Desktop / Cursor / Claude Code.

- `app.mcp.server.build_server()` — the MCPServer (tools, resources, prompts)
- `app.mcp.http.http_app()` / `mcp_lifespan()` — streamable HTTP, bearer PAT auth (mounted at /mcp)
- `app.mcp.stdio.main()` — `ledgic-mcp` stdio entry point (token from LEDGIC_MCP_TOKEN)
- `python -m app.mcp.tokens` — mint / revoke / list personal access tokens
"""
