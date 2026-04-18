from discharge_rag.preprocess import preprocess_note
from discharge_rag.chunking import chunk_text

def test_preprocess():
    note = "Diagnosis: HTN. Medications: Lisinopril 10 mg daily."
    p = preprocess_note(note)
    assert p.cleaned_text
    assert isinstance(p.sections, dict)

def test_chunking():
    chunks = chunk_text("word " * 1000, chunk_size=100, overlap=10)
    assert len(chunks) > 1
