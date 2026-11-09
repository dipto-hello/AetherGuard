"""
AetherGuard Governed MCP Server Entrypoint (stdio transport).

Allows external standard MCP clients (Claude Desktop, Cursor, LangGraph, etc.)
to connect to AetherGuard via JSON-RPC stdio. All consequential tool calls
are intercepted and governed by AetherGuard's Zero-Trust policy engine.
"""
import os
import sys
from app.sandbox.db import init_db
from app.governance.mcp_server import create_governed_mcp_server

def main():
    # Allow overriding database path via environment variable
    db_path = os.environ.get("AETHERGUARD_DB_PATH")
    authenticated_operator = os.environ.get("AETHERGUARD_AUTHENTICATED_OPERATOR")
    conn = init_db(db_path)
    try:
        server = create_governed_mcp_server(conn, authenticated_caller=authenticated_operator)
        server.run(transport="stdio")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
