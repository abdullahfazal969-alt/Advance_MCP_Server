import os
from pathlib import Path

# --- Path Configuration ---
# Dynamically determine the project root.
# This assumes config.py is in src/research_assistant/core/
# Path(__file__).resolve() -> .../src/research_assistant/core/config.py
# .parents[0] -> .../src/research_assistant/core/
# .parents[1] -> .../src/research_assistant/
# .parents[2] -> .../src/
# .parents[3] -> .../research_assistant_server/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Base directory where all tenant-specific data will be stored.
# Prioritize an environment variable (for production deployment)
# otherwise, default to a 'data' directory within the project root.
BASE_DATA_DIR = Path(os.getenv("MCP_BASE_DATA_DIR", PROJECT_ROOT / "data"))

# Ensure the base data directory exists. This creates it if it doesn't.
BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Multi-Tenancy Configuration ---
# This map defines the root directories for each simulated tenant.
# In a real multi-tenant system, this map would likely be loaded dynamically from a database
# or a secure configuration service, not hardcoded.
TENANT_ROOT_MAP = {
    "tenant_alpha": BASE_DATA_DIR / "tenant_alpha_docs",
    "tenant_beta": BASE_DATA_DIR / "tenant_beta_docs",
    # Add more tenants here as needed for testing
}

# Ensure each tenant's data directory also exists.
# This makes sure our test environment is ready automatically.
for tenant_id, tenant_path in TENANT_ROOT_MAP.items():
    tenant_path.mkdir(parents=True, exist_ok=True)
    # --- Other Server Configurations ---                                                                                      │
    # Example: Logging level, configurable via environment variable                                                            │
LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO")
