import asyncio
import logging

from fastmcp import FastMCP

from research_assistance.core.config import TENANT_ROOT_MAP
from research_assistance.core.logging import setup_logging
from research_assistance.tools.list_docs_tool import list_research_documents
from research_assistance.tools.summarize_docs_tool import summarize_document

# 1. Setup Logging - MUST be called early to configure logging before any other logs
setup_logging()
logger = logging.getLogger(__name__)

# 2. Instantiate FastMCP Server
mcp = FastMCP(
    name="ResearchAssistantServer",
)

# 3. Register Tools
mcp.tool(
    list_research_documents,
    description="Lists research-relevant files and directories in a tenant's research folder.",
)
mcp.tool(
    summarize_document,
    description="Locates a document in the tenant's folder, extracts its content, and uses AI sampling to provide a summary.",
)

# 4. Main execution block to run the server
if __name__ == "__main__":
    logger.info("Starting Research Assistant MCP Server...")
    # Ensure tenant data directories exist before running the server
    for tenant_id, tenant_path in TENANT_ROOT_MAP.items():
        if not tenant_path.exists():
            logger.warning(
                f"Tenant data directory does not exist, creating: {tenant_path}"
            )
            tenant_path.mkdir(parents=True, exist_ok=True)

    # Run the MCP server via STDIO (default) for easy manual testing
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Research Assistant MCP Server stopped.")
