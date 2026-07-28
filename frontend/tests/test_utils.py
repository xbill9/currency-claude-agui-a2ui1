from main import cleanup_final_text, extract_all_text, merge_strings


def test_extract_all_text():
    # Test valid event object
    event = {"content": {"parts": [{"text": "Hello "}, {"text": "world!"}]}}
    assert extract_all_text(event) == ["Hello ", "world!"]

    # Test missing content
    assert extract_all_text({}) == []

    # Test invalid structure
    assert extract_all_text({"content": "not a dict"}) == []
    assert extract_all_text({"content": {"parts": "not a list"}}) == []


def test_merge_strings():
    # No overlap
    assert merge_strings("Hello", "World") == "HelloWorld"

    # Simple overlap
    assert (
        merge_strings("Hello ", " world") == "Hello  world"
    )  # existing.rstrip() -> "Hello", incoming.lstrip() -> "world"
    # Wait, my merge_strings implementation:
    # e_norm = existing.rstrip() -> "Hello"
    # i_norm = incoming.lstrip() -> "world"
    # e_norm.endswith(i_norm[:size]) -> "Hello".endswith("w") -> False
    # So it returns existing + incoming -> "Hello  world"

    # Real overlap
    assert (
        merge_strings("This is a test", "test of the system")
        == "This is a test of the system"
    )
    assert (
        merge_strings("Multiple words overlap", "overlap with more text")
        == "Multiple words overlap with more text"
    )

    # Empty inputs
    assert merge_strings("", "New") == "New"
    assert merge_strings("Existing", "") == "Existing"


def test_cleanup_final_text():
    raw_text = """
    🚀 Starting the course creation pipeline...
    This is the course content.
    🔍 Research is starting...
    More content here.
    [progress_agent] said: Working hard.
    For context: some leak.
    RESEARCH_FINDINGS_START
    leaked findings
    RESEARCH_FINDINGS_END
    Final footer.
    """
    cleaned = cleanup_final_text(raw_text)

    assert "🚀 Starting the course creation pipeline..." not in cleaned
    assert "🔍 Research is starting..." not in cleaned
    assert "[progress_agent] said:" not in cleaned
    assert "For context:" not in cleaned
    assert "RESEARCH_FINDINGS_START" not in cleaned
    assert "This is the course content." in cleaned
    assert "Final footer." in cleaned
