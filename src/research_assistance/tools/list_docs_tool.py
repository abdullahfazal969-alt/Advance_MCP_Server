import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastmcp import Context, FastMCP  # Removed 'tool' from import

from research_assistance.core.config import TENANT_ROOT_MAP  # RE-ADDED GLOBAL IMPORT
from research_assistance.core.exceptions import AccessDeniedError, DocumentNotFoundError
from research_assistance.core.security import validate_path

# This mcp instance will eventually be configured and run in src/research_assistance/server.py
# For now, it allows us to define tools.
mcp = FastMCP(name="ResearchAssistant")


def _list_directory_recursive(
    base_path: Path,
    current_path: Path,
    include_hidden: bool,
    allowed_file_types: Optional[List[str]],
) -> Dict:
    """Helper to recursively list files and directories, filtering by type."""
    current_listing = {"files": [], "directories": []}

    try:
        for item in current_path.iterdir():
            if not include_hidden and item.name.startswith("."):
                continue  # Skip hidden items

            if item.is_file():
                is_allowed = False
                if (
                    allowed_file_types is None
                ):  # No specific filtering, all files are allowed
                    is_allowed = True
                else:
                    # Check if the full item name (e.g., '.config_file') is in allowed_file_types
                    # OR if its suffix (e.g., '.md' for 'article.md') is in allowed_file_types
                    if (
                        item.suffix.lower() in allowed_file_types
                        or item.name.lower() in allowed_file_types
                    ):
                        is_allowed = True

                if is_allowed:
                    relative_item_path = str(item.relative_to(base_path))
                    current_listing["files"].append(
                        {
                            "name": item.name,  # Corrected: use item.name
                            "size": item.stat().st_size,
                            # 'last_modified': item.stat().st_mtime # V2/Enhancement
                        }
                    )
            elif item.is_dir():
                # Recursively call for subdirectories
                subdir_contents = _list_directory_recursive(
                    base_path, item, include_hidden, allowed_file_types
                )
                # Only include directory if it or its children contain allowed file types
                if subdir_contents["files"] or subdir_contents["directories"]:
                    relative_item_path = str(item.name)  # Corrected: use item.name
                    current_listing["directories"].append(
                        {
                            "name": item.name,  # FIX: Use item.name for the bare directory name
                            "contents": subdir_contents,
                        }
                    )
    except FileNotFoundError:
        # This should ideally be caught before calling this helper if base_path is wrong
        pass  # Or re-raise with more context
    except Exception as e:
        # Catch other FS errors and wrap them
        raise DocumentNotFoundError(f"Error accessing directory {current_path}: {e}")

    return current_listing


@mcp.tool(
    "list_research_documents",
    description="Lists research-relevant files and directories in a tenant's research folder.",
)
async def list_research_documents(
    tenant_id: str,
    *,  # Enforce keyword-only arguments after tenant_id
    relative_path: str = ".",  # Default to current directory
    recursive: bool = True,
    include_hidden: bool = False,
    allowed_file_types: Optional[List[str]] = None,  # NEW: Filter by file type
    ctx: Context,
) -> Dict:
    """
    Deterministically lists research-relevant files and directories within a tenant's allowed research root.
    """
    if ctx:
        await ctx.info(
            f"[{tenant_id}] Listing documents in '{relative_path}' (recursive={recursive}, hidden={include_hidden}, types={allowed_file_types})"
        )

    # Define default research-relevant file types if not provided
    if allowed_file_types is None:
        allowed_file_types = [
            ".md",
            ".txt",
            ".pdf",
            ".csv",
            ".json",
            ".docx",
            ".pptx",
            ".xlsx",
        ]
        allowed_file_types = [ft.lower() for ft in allowed_file_types]

    try:
        # 1. Validate Path (Security & Multi-Tenancy)
        # We pass TENANT_ROOT_MAP (globally imported) to validate_path.
        base_dir_for_listing = validate_path(tenant_id, relative_path)

        # 2. Check if the resolved path actually exists and is a directory for listing
        if not base_dir_for_listing.exists():
            raise DocumentNotFoundError(
                f"Path does not exist: '{relative_path}' for tenant '{tenant_id}'."
            )

        if not base_dir_for_listing.is_dir():
            # If it's a file, check if it's an allowed type, otherwise raise error
            if base_dir_for_listing.is_file() and (
                base_dir_for_listing.suffix.lower() in allowed_file_types
                or base_dir_for_listing.name.lower() in allowed_file_types
            ):
                # If path points to a single research file, return info about just that file
                return {
                    "files": [
                        {
                            "name": str(base_dir_for_listing.name),
                            "size": base_dir_for_listing.stat().st_size,
                        }
                    ],
                    "directories": [],
                }
            else:
                raise DocumentNotFoundError(
                    f"Path is not a research-relevant directory or file: '{relative_path}' for tenant '{tenant_id}'."
                )

        # 3. Listing Logic
        if recursive:
            return _list_directory_recursive(
                base_path=base_dir_for_listing,
                current_path=base_dir_for_listing,
                include_hidden=include_hidden,
                allowed_file_types=allowed_file_types,
            )
        else:
            # Non-recursive listing (only immediate children), filtered
            results = {"files": [], "directories": []}
            for item in base_dir_for_listing.iterdir():
                if not include_hidden and item.name.startswith("."):
                    continue

                if item.is_file() and (
                    item.suffix.lower() in allowed_file_types
                    or item.name.lower() in allowed_file_types
                ):
                    results["files"].append(
                        {
                            "name": item.name,  # Corrected: use item.name
                            "size": item.stat().st_size,
                        }
                    )
                elif item.is_dir():
                    results["directories"].append(
                        {
                            "name": item.name,  # Corrected: use item.name
                            "contents": {"files": [], "directories": []},
                        }
                    )
            return results

    except AccessDeniedError as e:
        if ctx:
            await ctx.error(
                f"[{tenant_id}] Access denied: {e}"
            )  # FIX: Changed 'error=e' to 'exc_info=True'
        raise
    except DocumentNotFoundError as e:
        if ctx:
            await ctx.error(
                f"[{tenant_id}] Document not found: {e}"
            )  # FIX: Changed 'error=e' to 'exc_info=True'
        raise
    except Exception as e:
        if ctx:
            await ctx.error(
                f"[{tenant_id}] Unexpected error listing '{relative_path}': {e}"
            )  # FIX: Changed 'error=e' to 'exc_info=True'
        raise DocumentNotFoundError(f"Error processing request: {e}")
    finally:
        if ctx:
            await ctx.info(
                f"[{tenant_id}] Finished listing documents for '{relative_path}'"
            )
            await ctx.info(
                f"[{tenant_id}] Finished listing documents for '{relative_path}'"
            )
            await ctx.info(
                f"[{tenant_id}] Finished listing documents for '{relative_path}'"
            )
