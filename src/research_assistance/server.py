import logging

from fastmcp import FastMCP

from research_assistance.core.config import TENANT_ROOT_MAP
from research_assistance.core.logging import setup_logging
from research_assistance.tools.list_docs_tool import list_research_documents

from research_assistance.tools.summarize_docs_tool import summarize_document

print("Starting")
# 1. Setup Logging early
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
