import os
from pathlib import Path
from typing import Dict, List, Optional

from fastmcp import Context

from research_assistance.core.config import TENANT_ROOT_MAP
from research_assistance.core.exceptions import AccessDeniedError, DocumentNotFoundError
from research_assistance.core.security import validate_path


def _list_directory_recursive(
    base_path: Path,
    current_path: Path,
    include_hidden: bool,
    allowed_file_types: Optional[List[str]],
) -> Dict:
    """Helper to recursively list files and directories, filtering by type."""
    current_listing = {"files": [], "directories": []}

    for item in current_path.iterdir():
        if not include_hidden and item.name.startswith("."):
            continue

        if item.is_file():
            if allowed_file_types is None or item.suffix.lower() in allowed_file_types:
                current_listing["files"].append(
                    {"name": item.name, "size": item.stat().st_size}
                )
        elif item.is_dir():
            subdir_contents = _list_directory_recursive(
                base_path, item, include_hidden, allowed_file_types
            )
            if subdir_contents["files"] or subdir_contents["directories"]:
                current_listing["directories"].append(
                    {"name": item.name, "contents": subdir_contents}
                )

    return current_listing


async def list_research_documents(
    tenant_id: str,
    *,
    relative_path: str = ".",
    recursive: bool = True,
    include_hidden: bool = False,
    allowed_file_types: Optional[List[str]] = None,
    ctx: Context,
) -> Dict:
    """
    Lists research-relevant files and directories within a tenant's allowed research root.
    """
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

    try:
        base_dir_for_listing = validate_path(tenant_id, relative_path)
        if not base_dir_for_listing.exists():
            raise DocumentNotFoundError(f"Path does not exist: {relative_path}")

        if recursive:
            return _list_directory_recursive(
                base_dir_for_listing,
                base_dir_for_listing,
                include_hidden,
                [ft.lower() for ft in allowed_file_types],
            )
        else:
            results = {"files": [], "directories": []}
            for item in base_dir_for_listing.iterdir():
                if not include_hidden and item.name.startswith("."):
                    continue
                if item.is_file() and (
                    item.suffix.lower() in allowed_file_types
                    or item.name.lower() in allowed_file_types
                ):
                    results["files"].append(
                        {"name": item.name, "size": item.stat().st_size}
                    )
                elif item.is_dir():
                    results["directories"].append(
                        {
                            "name": item.name,
                            "contents": {"files": [], "directories": []},
                        }
                    )
            return results

    except Exception as e:
        if ctx:
            await ctx.error(f"[{tenant_id}] Error listing documents: {e}")
        raise
