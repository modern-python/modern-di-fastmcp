import modern_di_fastmcp


def test_public_surface() -> None:
    assert sorted(modern_di_fastmcp.__all__) == ["FromDI", "fastmcp_context_provider", "fetch_di_container", "setup_di"]
