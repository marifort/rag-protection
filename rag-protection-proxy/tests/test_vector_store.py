import pytest

pytest.importorskip("qdrant_client")
from qdrant_client import QdrantClient

from rag_protection_proxy.embeddings import HashEmbedder
from rag_protection_proxy.vector_store import VectorDocumentStore, build_acl_filter


@pytest.fixture
def vector_store() -> VectorDocumentStore:
    return VectorDocumentStore(
        client=QdrantClient(":memory:"),
        collection="test-chunks",
        embedder=HashEmbedder(),
    )


def test_build_acl_filter_includes_public_and_all_staff():
    acl_filter = build_acl_filter(["engineering"])
    should = acl_filter.should or []
    match_any = should[0].match
    assert "engineering" in match_any.any
    assert "public" in match_any.any
    assert "all-staff" in match_any.any
    must_not = acl_filter.must_not or []
    assert must_not[0].key == "status"


def test_vector_store_acl_filtered_search(vector_store: VectorDocumentStore):
    vector_store.ingest("public-faq", "FAQ", "support hours are 9 to 6", ["all-staff"])
    vector_store.ingest("hr-payroll", "Payroll", "payroll total 4.2M confidential", ["hr"])

    eng = vector_store.search("payroll total 4.2M confidential", ["engineering"], top_k=5)
    hr = vector_store.search("payroll total 4.2M confidential", ["hr"], top_k=5)

    assert all(hit.document_id != "hr-payroll" for hit in eng)
    assert hr[0].document_id == "hr-payroll"
    assert "4.2M" in hr[0].text


def test_vector_store_search_with_trace_acl_exclusion(vector_store: VectorDocumentStore):
    vector_store.ingest("public-faq", "FAQ", "support hours are 9 to 6", ["all-staff"])
    vector_store.ingest("hr-payroll", "Payroll", "payroll total 4.2M confidential", ["hr"])

    chunks, trace = vector_store.search_with_trace(
        "payroll total 4.2M confidential",
        ["engineering", "all-staff"],
        top_k=2,
    )
    outcomes = {row.document_id: row.outcome for row in trace}
    assert outcomes.get("hr-payroll") == "excluded_acl"
    assert all(chunk.document_id != "hr-payroll" for chunk in chunks)
    assert all(row.detail != "trace unavailable for store backend" for row in trace)


def test_vector_store_search_with_trace_quarantine_exclusion(vector_store: VectorDocumentStore):
    vector_store.ingest(
        "quarantined-doc",
        "Quarantined",
        "secret material payroll confidential",
        ["all-staff"],
        metadata={"status": "quarantined"},
    )
    vector_store.ingest("public-faq", "FAQ", "support hours weekdays", ["all-staff"])
    _, trace = vector_store.search_with_trace(
        "secret material payroll",
        ["all-staff"],
        top_k=2,
    )
    assert any(row.outcome == "excluded_quarantine" for row in trace)


def test_vector_store_list_and_count(vector_store: VectorDocumentStore):
    vector_store.ingest("a", "Alpha", "alpha content", ["engineering"])
    vector_store.ingest("b", "Beta", "beta content", ["hr"])

    assert vector_store.count_documents() == 2
    docs = vector_store.list_documents()
    by_id = {doc["document_id"]: doc for doc in docs}
    assert by_id["a"]["chunk_count"] >= 1
    assert by_id["b"]["allowed_groups"] == ["hr"]


def test_vector_store_semantic_paraphrase_retrieval():
    pytest.importorskip("sentence_transformers")
    try:
        store = VectorDocumentStore(
            client=QdrantClient(":memory:"),
            collection="semantic-test",
        )
    except Exception as exc:
        pytest.skip(f"SentenceTransformer model unavailable offline: {exc}")
    store.ingest(
        "public-faq",
        "Company FAQ",
        "Support is available Monday through Friday, 9am to 6pm Eastern.",
        ["all-staff", "public"],
    )

    hits = store.search("When is the helpdesk open?", ["engineering", "all-staff"], top_k=3)
    assert hits
    assert hits[0].document_id == "public-faq"
