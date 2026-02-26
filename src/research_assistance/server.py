import asyncio
import logging 
from fastmcp import FastMCP
from research_assistance.core.logging import setup_logging
from research_assistance.core.config import TENANT_ROOT_MAP 
from research_assistance.tools.list_docs_tool import list_research_documents 

# 1. Setup Logging - MUST be called early to configure logging before any other logs
setup_logging()
logger = logging.getLogger(__name__) 

# 2. Instantiate FastMCP Server
mcp = FastMCP(
    name="ResearchAssistantServer",
)

# 3. Register Tools
mcp.tool(list_research_documents, description="Lists research-relevant files and directories in a tenant's research folder.")

# 4. Main execution block to run the server
if __name__ == "__main__":
    logger.info("Starting Research Assistant MCP Server...")
    # Ensure tenant data directories exist before running the server
    for tenant_id, tenant_path in TENANT_ROOT_MAP.items():
        if not tenant_path.exists():
            logger.warning(f"Tenant data directory does not exist, creating: {tenant_path}")
            tenant_path.mkdir(parents=True, exist_ok=True)
    
    # Run the MCP server in HTTP mode for interaction via mcp dev client
    logger.info("Server running in HTTP mode on http://0.0.0.0:8000")
    mcp.run(transport="http", host="0.0.0.0", port=8000) # This will run until interrupted (Ctrl+C)
    logger.info("Research Assistant MCP Server stopped.")