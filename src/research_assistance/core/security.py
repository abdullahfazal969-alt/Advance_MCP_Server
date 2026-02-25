from pathlib import Path
from research_assistance.core.config import TENANT_ROOT_MAP # IMPORT GLOBALLY AGAIN
from research_assistance.core.exceptions import AccessDeniedError
from typing import Dict # Still needed for other type hints if any

def validate_path(tenant_id: str, user_path: str) -> Path: # REMOVE tenant_roots arg
    """
    Validates that the user_path is within the allowed research directory
    for the given tenant, preventing directory traversal attacks.

    Args:
        tenant_id (str): The ID of the tenant making the request.
        user_path (str): The path requested by the user.
        # REMOVED tenant_roots: Dict[str, Path] from signature

    Returns:
        Path: The resolved, validated absolute path within the allowed root.

    Raises:
        AccessDeniedError: If the tenant_id is invalid or the requested path
                           is outside the allowed root.
    """
    if tenant_id not in TENANT_ROOT_MAP: # Use global TENANT_ROOT_MAP
        raise AccessDeniedError(f"Invalid tenant ID: '{tenant_id}'. Access denied.")

    tenant_root = TENANT_ROOT_MAP[tenant_id] # Use global TENANT_ROOT_MAP

    # Ensure the tenant's root directory actually exists
    if not tenant_root.is_dir():
        raise AccessDeniedError(f"Tenant root directory not found for '{tenant_id}': {tenant_root}")

    # NEW SECURITY CHECK: Prevent user_path from overriding the tenant_root
    # by being an absolute path or starting with '..'
    if user_path.startswith('/') or user_path.startswith('..') or (Path(user_path).is_absolute() and user_path != ""):
        raise AccessDeniedError(f"Access denied for tenant '{tenant_id}': Absolute or parent path '{user_path}' not allowed.")

    requested_full_path = tenant_root / user_path # Safely join now that user_path is relative

    resolved_path = requested_full_path.resolve()
    resolved_tenant_root = tenant_root.resolve()

    # NEW ROBUST CHECK: Use is_relative_to for robust security check (Python 3.9+)
    if not resolved_path.is_relative_to(resolved_tenant_root):
        raise AccessDeniedError(
            f"Access denied for tenant '{tenant_id}': '{user_path}' "
            f"resolves outside allowed root '{resolved_tenant_root}'."
        )

    return resolved_path
