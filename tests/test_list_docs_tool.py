import pytest
from pathlib import Path
from research_assistance.core.exceptions import AccessDeniedError, DocumentNotFoundError
from research_assistance.core.security import validate_path 
from research_assistance.core.config import TENANT_ROOT_MAP # Needed for monkeypatching in the fixture setup
from research_assistance.tools.list_docs_tool import list_research_documents
from fastmcp import Context # For mocking ctx

@pytest.fixture
def mock_multi_tenant_data(tmp_path, monkeypatch): # Renamed fixture for clarity
    """
    Creates a temporary directory structure for testing multi-tenant file access
    and provides the mocked TENANT_ROOT_MAP.
    """
    base_test_data = tmp_path / "data"
    
    tenant_alpha_root = base_test_data / "tenant_alpha_docs"
    tenant_alpha_root.mkdir(parents=True, exist_ok=True)
    
    # Create research-relevant files
    (tenant_alpha_root / "article.md").write_text("Markdown content")
    (tenant_alpha_root / "report.txt").write_text("Text content")
    (tenant_alpha_root / "thesis.pdf").write_bytes(b"%PDF-1.4\n...") # Simulate PDF
    (tenant_alpha_root / "data.csv").write_text("header,value\n1,10")
    
    # Create non-research-relevant files
    (tenant_alpha_root / "image.png").write_bytes(b"PNG")
    (tenant_alpha_root / "program.exe").write_bytes(b"EXE")
    (tenant_alpha_root / ".config_file").write_text("hidden config") # Hidden file
    
    (tenant_alpha_root / "subdir").mkdir()
    (tenant_alpha_root / "subdir" / "note.txt").write_text("Subdir note")
    (tenant_alpha_root / "subdir" / "temp.log").write_text("Log file") # Non-research
    
    tenant_beta_root = base_test_data / "tenant_beta_docs"
    tenant_beta_root.mkdir(parents=True, exist_ok=True)
    (tenant_beta_root / "beta_report.txt").write_text("Beta content")
    
    # Directory that is empty
    empty_dir_root = base_test_data / "empty_tenant_docs"
    empty_dir_root.mkdir(parents=True, exist_ok=True)

    # For traversal tests from security.py
    forbidden_area_for_symlink = tmp_path / "forbidden_area"
    forbidden_area_for_symlink.mkdir()
    (forbidden_area_for_symlink / "secret.txt").write_text("secret content")
    # This symlink points outside the tenant_alpha_root, validate_path should catch it
    (tenant_alpha_root / "symlink_to_secret").symlink_to(forbidden_area_for_symlink / "secret.txt")

    # This 'global_forbidden_area' is outside any tenant root, for traversal tests
    global_forbidden_area = tmp_path / "global_forbidden_area"
    global_forbidden_area.mkdir()
    (global_forbidden_area / "another_secret.txt").write_text("global secret content")

    mock_tenant_roots = {
        "tenant_alpha": tenant_alpha_root,
        "tenant_beta": tenant_beta_root,
        "empty_tenant": empty_dir_root,
        "non_existent_root_tenant": tmp_path / "non_existent_folder"
    }
    
    # Monkeypatch TENANT_ROOT_MAP for the duration of these tests
    # This is important for validate_path which imports it globally
    # Although validate_path now takes it as an arg, this is still good for overall test environment consistency
    monkeypatch.setattr('research_assistance.core.config.TENANT_ROOT_MAP', mock_tenant_roots)
    
    yield mock_tenant_roots # Yield the mocked roots dictionary

# Mock the Context object as it's injected by FastMCP
@pytest.fixture
def mock_context():
    """Mocks the FastMCP Context object for testing."""
    class DummyContext:
        def info(self, *a, **kw): pass # Synchronous
        def error(self, *a, **kw): pass # Synchronous
        async def report_progress(self, *a, **kw): pass # Keep async if used by another tool

    return DummyContext()

# Helper function to flatten recursive results for assertions
def _flatten_files(listing_result: Dict) -> set[str]:
    files = {f["name"] for f in listing_result["files"]}
    for d in listing_result["directories"]:
        files.update(_flatten_files(d["contents"]))
    return files

# --- Actual Test Functions ---

@pytest.mark.asyncio
async def test_list_research_documents_non_recursive_root(mock_multi_tenant_data, mock_context): # Fixture passed as arg
    """Tests non-recursive listing from the root of tenant_alpha."""
    mock_roots = mock_multi_tenant_data
    result = await list_research_documents(
        tenant_id="tenant_alpha", 
        relative_path=".", 
        recursive=False, 
        ctx=mock_context,
        allowed_file_types=[".md", ".txt"], # Specific types
    )
    
    # Assert files
    file_names = {f["name"] for f in result["files"]}
    assert "article.md" in file_names
    assert "report.txt" in file_names
    assert "thesis.pdf" not in file_names # Not in allowed_file_types
    assert "data.csv" not in file_names # Not in allowed_file_types
    assert "image.png" not in file_names
    assert "program.exe" not in file_names
    assert ".config_file" not in file_names # Hidden

    # Assert directories
    dir_names = {d["name"] for d in result["directories"]}
    assert "subdir" in dir_names
    assert len(result["directories"]) == 1 # Only one subdir

@pytest.mark.asyncio
async def test_list_research_documents_recursive_root(mock_multi_tenant_data, mock_context):
    """Tests recursive listing from the root of tenant_alpha."""
    mock_roots = mock_multi_tenant_data
    result = await list_research_documents(
        tenant_id="tenant_alpha", 
        relative_path=".", 
        recursive=True, 
        ctx=mock_context,
    )
    
    # Assert files - now flatten the result
    file_names = _flatten_files(result) # Use helper
    assert "article.md" in file_names
    assert "report.txt" in file_names
    assert "thesis.pdf" in file_names # Default includes PDF
    assert "data.csv" in file_names # Default includes CSV
    assert "note.txt" in file_names # FIX: Changed from "subdir/note.txt" to "note.txt"
    assert "image.png" not in file_names # Not default
    assert "program.exe" not in file_names # Not default
    assert ".config_file" not in file_names # Hidden

    # Assert directories
    dir_names = {d["name"] for d in result["directories"]}
    assert "subdir" in dir_names
    assert len(result["directories"]) == 1 # Only one subdir

    # Check nested content - this also needs to be updated for name
    subdir_result = next((d["contents"] for d in result["directories"] if d["name"] == "subdir"), None)
    assert subdir_result is not None
    assert {f["name"] for f in subdir_result["files"]} == {"note.txt"} # FIX: Changed from "subdir/note.txt" to "note.txt"
    
@pytest.mark.asyncio
async def test_list_research_documents_non_recursive_subdir(mock_multi_tenant_data, mock_context):
    """Tests non-recursive listing from a subdirectory."""
    mock_roots = mock_multi_tenant_data
    result = await list_research_documents(
        tenant_id="tenant_alpha", 
        relative_path="subdir", 
        recursive=False, 
        ctx=mock_context,
    )
    
    file_names = {f["name"] for f in result["files"]}
    assert "note.txt" in file_names
    assert len(file_names) == 1
    assert len(result["directories"]) == 0


@pytest.mark.asyncio
async def test_list_research_documents_empty_directory(mock_multi_tenant_data, mock_context):
    """Tests listing an empty directory."""
    mock_roots = mock_multi_tenant_data
    result = await list_research_documents(
        tenant_id="empty_tenant", 
        relative_path=".", 
        recursive=False, 
        ctx=mock_context,
    )
    assert result["files"] == []
    assert result["directories"] == []

@pytest.mark.asyncio
async def test_list_research_documents_non_existent_path(mock_multi_tenant_data, mock_context):
    """Tests listing a non-existent path within the allowed root."""
    mock_roots = mock_multi_tenant_data
    with pytest.raises(DocumentNotFoundError, match="Path does not exist"):
        await list_research_documents(
            tenant_id="tenant_alpha", 
            relative_path="non_existent_folder", 
            ctx=mock_context
        )

@pytest.mark.asyncio
async def test_list_research_documents_access_denied_traversal(mock_multi_tenant_data, mock_context):
    """Tests that path traversal is caught by validate_path."""
    mock_roots = mock_multi_tenant_data
    with pytest.raises(AccessDeniedError):
        await list_research_documents(
            tenant_id="tenant_alpha", 
            relative_path="../forbidden_area/secret.txt", 
            ctx=mock_context
        )

@pytest.mark.asyncio
async def test_list_research_documents_access_denied_invalid_tenant(mock_multi_tenant_data, mock_context):
    """Tests that an invalid tenant ID is caught."""
    mock_roots = mock_multi_tenant_data
    with pytest.raises(AccessDeniedError, match="Invalid tenant ID"):
        await list_research_documents(
            tenant_id="unknown_tenant", 
            relative_path=".", 
            ctx=mock_context
        )

@pytest.mark.asyncio
async def test_list_research_documents_include_hidden(mock_multi_tenant_data, mock_context):
    """Tests listing with include_hidden=True."""
    mock_roots = mock_multi_tenant_data
    result = await list_research_documents(
        tenant_id="tenant_alpha", 
        relative_path=".", 
        recursive=False, 
        include_hidden=True, 
        ctx=mock_context,
        allowed_file_types=[".config_file"], # To include hidden specifically
    )
    file_names = {f["name"] for f in result["files"]}
    assert ".config_file" in file_names
    assert len(file_names) == 1

@pytest.mark.asyncio
async def test_list_research_documents_path_is_file(mock_multi_tenant_data, mock_context):
    """Tests when relative_path points directly to a research-relevant file."""
    mock_roots = mock_multi_tenant_data
    result = await list_research_documents(
        tenant_id="tenant_alpha", 
        relative_path="article.md", 
        ctx=mock_context,
    )
    assert len(result["files"]) == 1
    assert result["files"][0]["name"] == "article.md"
    assert result["directories"] == []


@pytest.mark.asyncio
async def test_list_research_documents_path_is_non_research_file(mock_multi_tenant_data, mock_context):
    """Tests when relative_path points directly to a non-research-relevant file."""
    mock_roots = mock_multi_tenant_data
    with pytest.raises(DocumentNotFoundError, match="Path is not a research-relevant directory or file"):
        await list_research_documents(
            tenant_id="tenant_alpha", 
            relative_path="image.png", 
            ctx=mock_context,
        )

@pytest.mark.asyncio
async def test_list_research_documents_non_recursive_mixed_files_filtered(mock_multi_tenant_data, mock_context):
    """Tests non-recursive listing with mixed files and default filtering."""
    mock_roots = mock_multi_tenant_data
    result = await list_research_documents(
        tenant_id="tenant_alpha", 
        relative_path=".", 
        recursive=False, 
        ctx=mock_context,
    )
    
    file_names = {f["name"] for f in result["files"]}
    assert "article.md" in file_names
    assert "report.txt" in file_names
    assert "thesis.pdf" in file_names
    assert "data.csv" in file_names
    assert "image.png" not in file_names
    assert "program.exe" not in file_names
    assert ".config_file" not in file_names
    assert "subdir" in {d["name"] for d in result["directories"]}
