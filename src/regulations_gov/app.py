import os

from dotenv import load_dotenv
from fastmcp import FastMCP

from regulations_gov.tools import register_tools
from regulations_gov.routes import register_routes

load_dotenv()

mcp = FastMCP(
    "regulations_gov_mcp",
    instructions=(
        "This server provides access to regulations.gov, the official US federal portal for "
        "public participation in the rulemaking process. Use it to search and retrieve federal "
        "regulatory documents, public comments, and dockets.\n\n"
        "Start with regulations_search_dockets to discover dockets by topic or agency, "
        "then use regulations_search_documents to find documents within a docket, "
        "and regulations_search_comments to read public input on proposed rules.\n\n"
        "Authentication: Set REGULATIONS_GOV_API_KEY environment variable. "
        "Get a free key at https://api.data.gov/signup/"
    ),
)

# Register tools 
register_tools(mcp)

# Register routes 
register_routes(mcp)


if __name__ == "__main__":
    # When run directly, check for a platform port env var.
    # If found, start an HTTP server (useful for Databricks local testing).
    # Otherwise fall back to stdio for local MCP clients (Claude Desktop, etc.).
    port_env = os.getenv("DATABRICKS_APP_PORT") or os.getenv("PORT")
    if port_env:
        mcp.run(transport="http", host="0.0.0.0", port=int(port_env))
    else:
        mcp.run(transport="stdio")