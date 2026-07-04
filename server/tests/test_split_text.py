from server.services.rag import split_text


def test_empty_input_gives_no_chunks():
    assert split_text("") == []
    assert split_text("   \n  ") == []


def test_short_text_single_chunk():
    assert split_text("短文本", chunk_size=100, overlap=10) == ["短文本"]


def test_chunks_respect_max_size():
    text = "a" * 2000
    chunks = split_text(text, chunk_size=600, overlap=100)
    assert all(len(chunk) <= 600 for chunk in chunks)


def test_overlap_carries_context_between_chunks():
    text = "x" * 1200
    chunks = split_text(text, chunk_size=600, overlap=100)
    assert len(chunks) >= 2
    # Reconstructed length exceeds the original because of overlap.
    assert sum(len(chunk) for chunk in chunks) > len(text)


def test_prefers_paragraph_boundary():
    first = "第一段。" * 60   # ~240 chars
    second = "第二段内容。" * 60
    text = f"{first}\n\n{second}"
    chunks = split_text(text, chunk_size=300, overlap=50)
    # The first chunk should end at the paragraph break, not mid-sentence.
    assert chunks[0].endswith("第一段。")


def test_text_endpoints_preserved():
    # Overlap duplicates boundary segments, so instead of substring-matching the
    # concatenation we assert the first/last chunks keep the document endpoints.
    text = "".join(f"句子{i}。" for i in range(300))
    chunks = split_text(text, chunk_size=400, overlap=80)
    assert chunks[0].startswith("句子0。")
    assert chunks[-1].endswith("句子299。")
