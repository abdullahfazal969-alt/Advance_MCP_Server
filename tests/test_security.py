import pytest
from pathlib import Path
from research_assistance.core.security import validate_path
from research_assistance.core.exceptions import AccessDeniedError
from research_assistance.core import config # Import config to monkeypatch TENANT_ROOT_MAP

@pytest.fixture
def mock_multi_tenant_data(tmp_path, monkeypatch):
    """
    Creates a temporary directory structure for testing tenant roots
    and temporarily modifies TENANT_ROOT_MAP using monkeypatch.
    """
    base_test_data = tmp_path / "data"
    
    tenant_alpha_root = base_test_data / "tenant_alpha_docs"
    tenant_alpha_root.mkdir(parents=True, exist_ok=True)
    (tenant_alpha_root / "doc1.txt").write_text("content of doc1")
    (tenant_alpha_root / "subdir").mkdir()
    (tenant_alpha_root / "subdir" / "doc2.txt").write_text("content of doc2")

    tenant_beta_root = base_test_data / "tenant_beta_docs"
    tenant_beta_root.mkdir(parents=True, exist_ok=True)
    (tenant_beta_root / "doc_b.txt").write_text("content of doc_b")

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
        "non_existent_root_tenant": tmp_path / "non_existent_folder" # This directory won't be created
    }
    
    # Use monkeypatch to replace the TENANT_ROOT_MAP in the config module
    monkeypatch.setattr(config, "TENANT_ROOT_MAP", mock_tenant_roots)
    
    yield # Test functions run here
    
    # Teardown (pytest handles tmp_path cleanup automatically)

# --- Actual Test Functions ---

def test_validate_path_valid_paths(mock_multi_tenant_data): # Fixture passed as arg
    """Tests various valid paths within tenant roots."""
    mock_roots = config.TENANT_ROOT_MAP # Access the monkeypatched map directly
    
    # Case 1: Root directory access (empty user_path)
    assert validate_path("tenant_alpha", "") == mock_roots["tenant_alpha"].resolve()
    
    # Case 2: Direct file access
    expected_path = mock_roots["tenant_alpha"] / "doc1.txt"
    assert validate_path("tenant_alpha", "doc1.txt") == expected_path.resolve()

    # Case 3: Subdirectory file access
    expected_path = mock_roots["tenant_alpha"] / "subdir" / "doc2.txt"
    assert validate_path("tenant_alpha", "subdir/doc2.txt") == expected_path.resolve()

    # Case 4: Another tenant's valid file
    expected_path = mock_roots["tenant_beta"] / "doc_b.txt"
    assert validate_path("tenant_beta", "doc_b.txt") == expected_path.resolve()

def test_validate_path_invalid_tenant_id(mock_multi_tenant_data):
    """Tests access with a non-existent tenant ID."""
    with pytest.raises(AccessDeniedError, match="Invalid tenant ID"):
        validate_path("unknown_tenant", "some_file.txt")

def test_validate_path_traversal_attacks(mock_multi_tenant_data):
    """Tests various path traversal attempts."""
    
    # Case: user_path starts with '..'
    with pytest.raises(AccessDeniedError, match="Absolute or parent path '.."):
        validate_path("tenant_alpha", "../forbidden_area/secret.txt")

    # Case: user_path starts with '/'
    with pytest.raises(AccessDeniedError, match="Absolute or parent path '/"):
        validate_path("tenant_alpha", "/etc/passwd")
    
    # Case: user_path is an absolute path (even if not starting with '/')
    with pytest.raises(AccessDeniedError, match="Absolute or parent path"):
        # Construct an absolute path that's outside the root
        abs_outside_path = mock_multi_tenant_data["tenant_alpha"].parent.parent / "global_forbidden_area" / "another_secret.txt"
        validate_path("tenant_alpha", str(abs_outside_path))

    # Case: Accessing another tenant's data via traversal
    with pytest.raises(AccessDeniedError, match="Absolute or parent path"):
        # Construct a path that looks like it goes to another tenant's root
        another_tenant_path = mock_multi_tenant_data["tenant_alpha"].parent / "tenant_beta_docs" / "doc_b.txt"
        validate_path("tenant_alpha", str(another_tenant_path))

    # Case: Accessing via symlink that points outside the root
    with pytest.raises(AccessDeniedError):
        validate_path("tenant_alpha", "symlink_to_secret")


def test_validate_path_non_existent_tenant_root_dir(mock_multi_tenant_data):
    """Tests when the tenant's root directory does not physically exist."""
    # 'non_existent_root_tenant' is in the mocked map but its directory doesn't exist
    with pytest.raises(AccessDeniedError, match="Tenant root directory not found"):
        validate_path("non_existent_root_tenant", "any_file.txt")

def test_validate_path_non_existent_file_in_valid_root(mock_multi_tenant_data):
    """Tests a non-existent file within an otherwise valid root (should succeed validation,
       the tool calling it would then handle FileNotFoundError)."""
    valid_path = validate_path("tenant_alpha", "non_existent_file.txt")
    assert valid_path == (config.TENANT_ROOT_MAP["tenant_alpha"] / "non_existent_file.txt").resolve()
    assert not valid_path.exists() # Confirm the file doesn't actually exist
