# mcp-server-regulations-gov

MCP server for the [regulations.gov](https://www.regulations.gov) API. Provides tools to search and retrieve federal regulatory documents, public comments, and dockets.

## Tools

| Tool | Description |
|------|-------------|
| `regulations_search_documents` | Search Rules, Proposed Rules, Notices by keyword, agency, date range, docket |
| `regulations_get_document` | Get full metadata for a specific document |
| `regulations_search_comments` | Search public comments by keyword, agency, docket, or document |
| `regulations_get_comment` | Get full text and metadata for a specific comment |
| `regulations_search_dockets` | Search dockets by keyword, agency, type |
| `regulations_get_docket` | Get full metadata for a specific docket |

## Setup

### 1. Get an API key

Register for a free key at [api.data.gov/signup](https://api.data.gov/signup/).

### 2. Set the environment variable

```bash
export REGULATIONS_GOV_API_KEY=your_key_here
```

Or create a `.env` file (never commit this):

```
REGULATIONS_GOV_API_KEY=your_key_here
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Run locally

```bash
uv run python main.py
```

### 5. Configure in Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "regulations-gov": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-server-regulations-gov", "python", "main.py"],
      "env": {
        "REGULATIONS_GOV_API_KEY": "your_key_here"
      }
    }
  }
}
```

## Rate Limits

- Standard endpoints: see [api.data.gov rate limits](https://api.data.gov/docs/rate-limits/)
- Comment endpoints: 50 requests/minute, 500 requests/hour
- Maximum 5,000 results per sequential query — use date range filters for large datasets
