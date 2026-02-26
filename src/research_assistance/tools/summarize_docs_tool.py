import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastmcp import Context
from mcp.types import EmbeddedResource, ImageContent, SamplingMessage, TextContent

from research_assistance.core.config import TENANT_ROOT_MAP
from research_assistance.core.exceptions import AccessDeniedError, DocumentNotFoundError
from research_assistance.core.security import validate_path

# Note: The mcp instance is defined in server.py and this tool is registered there.


def _find_file_recursively(root_path: Path, filename: str) -> Optional[Path]:
    """
    Recursively searches for a file by name starting from root_path.
    Returns the Path object if found, otherwise None.
    Matches against both exact filename and filename without extension.
    """
    for dirpath, _, filenames in os.walk(root_path):
        for f in filenames:
            # Check for exact match or match without extension
            if f == filename or Path(f).stem == filename:
                return Path(dirpath) / f
    return None


async def summarize_document(tenant_id: str, filename: str, ctx: Context) -> Dict:
    """
    Locates a document in the tenant's folder, extracts its content,
    and uses AI sampling to provide a summary.
    """
    if ctx:
        await ctx.info(f"[{tenant_id}] Starting summary for document: '{filename}'")

    try:
        # 1. Locate the file recursively from the tenant's root
        if tenant_id not in TENANT_ROOT_MAP:
            raise AccessDeniedError(f"Invalid tenant ID: '{tenant_id}'")

        tenant_root = TENANT_ROOT_MAP[tenant_id]
        file_path = _find_file_recursively(tenant_root, filename)

        if not file_path:
            raise DocumentNotFoundError(
                f"Document '{filename}' not found for tenant '{tenant_id}'."
            )

        # 2. Security Validation
        relative_path = str(file_path.relative_to(tenant_root))
        validate_path(tenant_id, relative_path)

        # 3. Extract Content
        if ctx:
            await ctx.info(f"[{tenant_id}] Reading content of '{file_path.name}'...")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"File '{filename}' is not a readable text document.")

        # 4. Sampling (Delegated LLM Inference)
        if ctx:
            await ctx.info(
                f"[{tenant_id}] Sending content to AI for summarization (Sampling)..."
            )
            await ctx.report_progress(50)

        # Construct the sampling request using proper MCP types
        sampling_response = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"Please provide a concise, professional summary of the following research document:\n\n{content}",
                    ),
                )
            ],
            max_tokens=500,
        )

        # 5. Handle and return response
        if ctx:
            await ctx.report_progress(100)

        # FIX: sampling_response.content is a single object (TextContent | ImageContent | EmbeddedResource)
        # in the version of the MCP library we are using, not a list.
        content_obj = sampling_response.content

        if isinstance(content_obj, TextContent):
            summary = content_obj.text
            if ctx:
                await ctx.info(f"[{tenant_id}] Summarization complete.")
            return {"filename": file_path.name, "summary": summary}
        else:
            raise ValueError(
                f"AI failed to generate a valid text summary. Received: {type(content_obj)}"
            )

    except AccessDeniedError as e:
        if ctx:
            await ctx.error(f"[{tenant_id}] Access denied: {e}")
        raise
    except DocumentNotFoundError as e:
        if ctx:
            await ctx.error(f"[{tenant_id}] Document not found: {e}")
        raise
    except Exception as e:
        if ctx:
            await ctx.error(f"[{tenant_id}] Unexpected error during summarization: {e}")
        raise DocumentNotFoundError(f"Error processing request: {e}")
