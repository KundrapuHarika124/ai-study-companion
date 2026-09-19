from app.services.documents import chunk_pages, tag_chunk_concepts


def test_chunking_preserves_page_and_drops_fragments():
    pages = [{"page": 1, "text": "Intro heading\n\n" + ("The TCP handshake uses SYN and ACK. " * 40) + "\n\nshort", "heading": "Intro heading", "ocr": False},
             {"page": 2, "text": "tiny", "heading": "", "ocr": False}]
    chunks = chunk_pages(pages)
    assert chunks and all(c["page"] == 1 for c in chunks)
    assert all(len(c["text"]) >= 60 for c in chunks)
    assert all(len(c["text"]) <= 1200 for c in chunks)


def test_concept_tagging():
    concepts = [{"name": "TCP handshake", "keywords": ["syn", "ack"]}, {"name": "Subnetting", "keywords": ["cidr"]}]
    assert tag_chunk_concepts("The client sends a SYN packet", concepts) == ["TCP handshake"]
    assert tag_chunk_concepts("nothing relevant", concepts) == []
