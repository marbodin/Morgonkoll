from src.chunking import semantic_chunks


def test_chunking_preserves_order_and_semantic_boundaries() -> None:
    text = (
        "# Inledning\n\n"
        "Det här är första meningen. Det här är den andra meningen, med mer information.\n\n"
        "Kl. 07.30 börjar nästa del. Är du redo?"
    )
    chunks = semantic_chunks(text, max_chars=80)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    reconstructed = " ".join(chunk.text for chunk in chunks)
    assert "Inledning" in reconstructed
    assert "Kl. 07.30" in reconstructed
    assert chunks[0].pause_after_ms == 620
    assert chunks[-1].pause_after_ms == 430
    assert all(len(chunk.text) <= 80 for chunk in chunks)


def test_chunking_rejects_empty_text() -> None:
    try:
        semantic_chunks("   ")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("Expected empty narration to fail")

