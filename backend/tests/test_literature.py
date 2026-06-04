"""Tests for the literature search, translation, and collection API.

Covers: searching CNKI / PubMed / both (merged results, source selection,
pagination default 20/page, per-source totals, empty query → 200 empty), the
detail endpoint, abstract translation (bilingual content + Agent failure → 502),
MeSH term suggestion, and the literature-collection CRUD (create/list/delete,
folder create, save/remove item, cross-user isolation, nonexistent → 404, auth
required → 401).

The AgentCore client is injected via ``get_agentcore_client`` and overridden
with a fake returning canned ``AgentResponse`` objects whose ``response`` text
embeds the MCP tools' JSON output, so no real AWS/Bedrock calls are made and the
tolerant response parser is exercised end-to-end.

Requirements: 10.1-10.46
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.analysis import get_agentcore_client
from app.core.database import get_db
from app.main import app
from app.middleware.auth import get_current_user
from app.models.base import Base
from app.models.literature import CollectedLiterature, CollectionFolder, LiteratureCollection
from app.models.user import User
from app.services.agentcore_client import AgentResponse

# --- Canned literature records --------------------------------------------

CNKI_RECORD = {
    "title": "高血压患者的血压管理研究",
    "authors": ["张三", "李四"],
    "journal": "中华医学杂志",
    "publication_date": "2023-05-01",
    "abstract": "本研究探讨了高血压患者的血压管理策略。" * 20,
    "keywords": ["高血压", "血压管理"],
    "doi": "10.1000/cnki.2023.001",
    "data_source": "CNKI",
    "citation_count": 5,
}

PUBMED_RECORD = {
    "title": "Blood Pressure Management in Hypertensive Patients",
    "authors": ["Smith J", "Doe A"],
    "journal": "The Lancet",
    "publication_date": "2024-01-15",
    "abstract": "This study investigates blood pressure management strategies. " * 20,
    "keywords": ["hypertension", "blood pressure"],
    "doi": "10.1016/pubmed.2024.001",
    "data_source": "PubMed",
    "pmid": "38000001",
    "citation_count": 12,
}


def _search_response(records: list[dict]) -> AgentResponse:
    """Build an AgentResponse whose text embeds a JSON array of records."""
    text = (
        "已为您检索到以下文献：\n"
        + json.dumps({"results": records}, ensure_ascii=False)
        + "\n以上为检索结果。"
    )
    return AgentResponse(response=text, session_id="session-fake")


def _translation_response() -> AgentResponse:
    """Build an AgentResponse whose text embeds a bilingual translation object."""
    payload = {
        "translated_title": "Blood Pressure Management Study",
        "translated_abstract": "This is the translated abstract.",
    }
    text = "翻译结果如下：\n" + json.dumps(payload, ensure_ascii=False)
    return AgentResponse(response=text, session_id="session-fake")


def _mesh_response() -> AgentResponse:
    """Build an AgentResponse whose text embeds suggested MeSH terms."""
    payload = {"terms": ["Hypertension", "Blood Pressure", "Antihypertensive Agents"]}
    text = "推荐的 MeSH 术语：\n" + json.dumps(payload, ensure_ascii=False)
    return AgentResponse(response=text, session_id="session-fake")


class FakeAgentCoreClient:
    """Fake AgentCore client returning canned responses and recording calls.

    A single response can be supplied, or a routing callable that picks a
    response based on the invocation payload (used to return search vs.
    translation vs. MeSH results).
    """

    def __init__(self, response=None, router=None):
        self._response = response
        self._router = router
        self.calls: list[dict] = []

    async def invoke_agent(self, payload: dict, session_id: str = "") -> AgentResponse:
        self.calls.append({"payload": payload, "session_id": session_id})
        if self._router is not None:
            return self._router(payload)
        return self._response or AgentResponse(response="", session_id="session-fake")


class FailingAgentCoreClient:
    """Fake AgentCore client that raises, to exercise the 502 path."""

    def __init__(self):
        self.calls: list[dict] = []

    async def invoke_agent(self, payload: dict, session_id: str = "") -> AgentResponse:
        self.calls.append({"payload": payload, "session_id": session_id})
        raise RuntimeError("agent boom")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="lituser@example.com",
        password_hash="$2b$12$fakehash",
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session):
    """Create another user for isolation tests."""
    user = User(
        id=uuid.uuid4(),
        email="otherlit@example.com",
        password_hash="$2b$12$fakehash",
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _default_router(payload: dict) -> AgentResponse:
    """Route an invocation to the right canned response by its context."""
    context = payload.get("analysis_context", {})
    if "source_language" in context:
        return _translation_response()
    if "query" in context and "sources" not in context:
        return _mesh_response()
    # Search / detail: return both records by default.
    return _search_response([CNKI_RECORD, PUBMED_RECORD])


@pytest.fixture
def fake_client():
    """Shared fake AgentCore client routing by invocation context."""
    return FakeAgentCoreClient(router=_default_router)


def _build_client(db_session, user, agent_client):
    """Create a TestClient authenticated as ``user`` with the given fake agent."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_agentcore_client] = lambda: agent_client
    return TestClient(app)


@pytest.fixture
def client(db_session, test_user, fake_client):
    """Test client authenticated as test_user with a routing fake Agent client."""
    c = _build_client(db_session, test_user, fake_client)
    with c:
        yield c
    app.dependency_overrides.clear()


def _unauthenticated_client(db_session):
    """Create a client with only the DB overridden (no auth)."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _create_collection(client, name="我的收藏") -> dict:
    """Helper to create a collection and return the response JSON."""
    resp = client.post("/api/v1/literature/collections", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- POST /search ----------------------------------------------------------


class TestSearch:
    def test_search_both_sources_merges_results(self, client):
        resp = client.post(
            "/api/v1/literature/search",
            json={"keywords": "高血压", "sources": ["cnki", "pubmed"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 20
        labels = {r["data_source"] for r in data["results"]}
        assert labels == {"CNKI", "PubMed"}
        # Per-source totals keyed by label (Req 10.28).
        assert data["totals"] == {"CNKI": 1, "PubMed": 1}
        # Abstract preview limited to 200 chars (Req 10.22).
        for r in data["results"]:
            assert len(r["abstract_preview"]) <= 200

    def test_search_default_sources_both(self, client):
        # No sources provided → defaults to both (Req 10.7).
        resp = client.post("/api/v1/literature/search", json={"keywords": "高血压"})
        assert resp.status_code == 200
        assert resp.json()["totals"] == {"CNKI": 1, "PubMed": 1}

    def test_search_cnki_only_filters_merge(self, db_session, test_user):
        # Agent returns both, but selecting cnki only should keep only CNKI.
        agent = FakeAgentCoreClient(router=lambda p: _search_response([CNKI_RECORD, PUBMED_RECORD]))
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.post(
                "/api/v1/literature/search",
                json={"keywords": "高血压", "sources": ["cnki"]},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["data_source"] == "CNKI"
        assert data["totals"] == {"CNKI": 1}

    def test_search_invalid_source_rejected(self, client):
        resp = client.post(
            "/api/v1/literature/search",
            json={"keywords": "x", "sources": ["scholar"]},
        )
        assert resp.status_code == 400

    def test_search_pagination_default_20(self, db_session, test_user):
        # 25 records → first page returns 20, totals reflect full count.
        records = [
            {**PUBMED_RECORD, "title": f"Article {i}", "pmid": str(i)} for i in range(25)
        ]
        agent = FakeAgentCoreClient(router=lambda p: _search_response(records))
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.post(
                "/api/v1/literature/search",
                json={"keywords": "bp", "sources": ["pubmed"]},
            )
            page2 = c.post(
                "/api/v1/literature/search",
                json={"keywords": "bp", "sources": ["pubmed"], "page": 2},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 20
        assert len(data["results"]) == 20
        assert data["total"] == 25
        assert data["totals"] == {"PubMed": 25}
        # Second page holds the remaining 5.
        assert len(page2.json()["results"]) == 5

    def test_search_sort_by_date(self, db_session, test_user):
        older = {**PUBMED_RECORD, "title": "Older", "pmid": "1", "publication_date": "2020-01-01"}
        newer = {**PUBMED_RECORD, "title": "Newer", "pmid": "2", "publication_date": "2024-01-01"}
        agent = FakeAgentCoreClient(router=lambda p: _search_response([older, newer]))
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.post(
                "/api/v1/literature/search",
                json={"keywords": "bp", "sources": ["pubmed"], "sort_by": "date"},
            )
        app.dependency_overrides.clear()
        titles = [r["title"] for r in resp.json()["results"]]
        assert titles == ["Newer", "Older"]

    def test_search_empty_results_returns_200(self, db_session, test_user):
        # Plain-text response with no embedded JSON → empty list, still 200.
        agent = FakeAgentCoreClient(response=AgentResponse(response="未找到相关文献。"))
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.post("/api/v1/literature/search", json={"keywords": "zzz"})
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_search_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.post("/api/v1/literature/search", json={"keywords": "x"})
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- GET /{id} -------------------------------------------------------------


class TestDetail:
    def test_detail_returns_record(self, db_session, test_user):
        agent = FakeAgentCoreClient(router=lambda p: _search_response([PUBMED_RECORD]))
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.get("/api/v1/literature/38000001?source=pubmed")
        app.dependency_overrides.clear()
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data_source"] == "PubMed"
        assert data["external_id"] == "38000001"
        # Full abstract present (Req 10.26).
        assert data["abstract"]

    def test_detail_not_found(self, db_session, test_user):
        agent = FakeAgentCoreClient(response=AgentResponse(response="无此文献"))
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.get("/api/v1/literature/999?source=pubmed")
        app.dependency_overrides.clear()
        assert resp.status_code == 404

    def test_detail_requires_source(self, client):
        resp = client.get("/api/v1/literature/123")
        assert resp.status_code == 422

    def test_detail_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.get("/api/v1/literature/123?source=pubmed")
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- POST /{id}/translate --------------------------------------------------


class TestTranslate:
    def test_translate_pubmed_to_chinese(self, client):
        resp = client.post(
            "/api/v1/literature/38000001/translate",
            json={
                "title": "Blood Pressure Management",
                "abstract": "This study investigates blood pressure.",
                "source": "pubmed",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source_language"] == "en"
        assert data["target_language"] == "zh"
        assert data["original_title"] == "Blood Pressure Management"
        assert data["translated_title"] == "Blood Pressure Management Study"
        assert data["translated_abstract"] == "This is the translated abstract."

    def test_translate_cnki_to_english(self, client):
        resp = client.post(
            "/api/v1/literature/c1/translate",
            json={"title": "高血压研究", "abstract": "本研究...", "source": "cnki"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_language"] == "zh"
        assert data["target_language"] == "en"

    def test_translate_agent_failure_502(self, db_session, test_user):
        agent = FailingAgentCoreClient()
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.post(
                "/api/v1/literature/1/translate",
                json={"title": "t", "abstract": "a", "source": "pubmed"},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 502

    def test_translate_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.post("/api/v1/literature/1/translate", json={"title": "t"})
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- GET /mesh/suggest -----------------------------------------------------


class TestMeshSuggest:
    def test_mesh_suggest_returns_terms(self, client):
        resp = client.get("/api/v1/literature/mesh/suggest?q=hypertension")
        assert resp.status_code == 200, resp.text
        terms = resp.json()["terms"]
        assert "Hypertension" in terms
        assert len(terms) == 3

    def test_mesh_suggest_empty(self, db_session, test_user):
        agent = FakeAgentCoreClient(response=AgentResponse(response="无建议术语"))
        c = _build_client(db_session, test_user, agent)
        with c:
            resp = c.get("/api/v1/literature/mesh/suggest?q=xyz")
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json()["terms"] == []

    def test_mesh_suggest_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.get("/api/v1/literature/mesh/suggest?q=x")
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- Collections CRUD ------------------------------------------------------


class TestCollections:
    def test_create_and_list_collection(self, client):
        created = _create_collection(client, "心血管文献")
        assert created["name"] == "心血管文献"
        assert created["folders"] == []
        assert created["items"] == []

        resp = client.get("/api/v1/literature/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["collections"][0]["id"] == created["id"]

    def test_list_collections_sorted_desc(self, client, db_session, test_user):
        from datetime import datetime, timedelta, timezone

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ids = []
        for i in range(3):
            col = LiteratureCollection(
                user_id=test_user.id,
                name=f"col-{i}",
                created_at=base + timedelta(days=i),
            )
            db_session.add(col)
            db_session.commit()
            db_session.refresh(col)
            ids.append(str(col.id))

        resp = client.get("/api/v1/literature/collections")
        returned = [c["id"] for c in resp.json()["collections"]]
        assert returned == list(reversed(ids))

    def test_delete_collection(self, client, db_session):
        created = _create_collection(client)
        resp = client.delete(f"/api/v1/literature/collections/{created['id']}")
        assert resp.status_code == 204
        assert db_session.get(LiteratureCollection, uuid.UUID(created["id"])) is None

    def test_delete_collection_cascades_items(self, client, db_session):
        created = _create_collection(client)
        col_id = created["id"]
        client.post(
            f"/api/v1/literature/collections/{col_id}/items",
            json={"title": "T", "authors": ["A"], "source": "pubmed"},
        )
        resp = client.delete(f"/api/v1/literature/collections/{col_id}")
        assert resp.status_code == 204
        items = db_session.execute(
            select(CollectedLiterature).where(
                CollectedLiterature.collection_id == uuid.UUID(col_id)
            )
        ).scalars().all()
        assert items == []

    def test_delete_nonexistent_collection_404(self, client):
        resp = client.delete(f"/api/v1/literature/collections/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_cross_user_collection_denied(self, client, db_session, other_user, fake_client):
        created = _create_collection(client)
        other = _build_client(db_session, other_user, fake_client)
        resp = other.delete(f"/api/v1/literature/collections/{created['id']}")
        app.dependency_overrides.clear()
        assert resp.status_code == 403

    def test_collection_requires_auth(self, db_session):
        unauth = _unauthenticated_client(db_session)
        resp = unauth.get("/api/v1/literature/collections")
        assert resp.status_code == 401
        app.dependency_overrides.clear()


# --- Folders ---------------------------------------------------------------


class TestFolders:
    def test_create_folder(self, client, db_session):
        created = _create_collection(client)
        resp = client.post(
            "/api/v1/literature/collections/folders",
            json={"collection_id": created["id"], "name": "重要"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "重要"
        assert data["collection_id"] == created["id"]
        folder = db_session.get(CollectionFolder, uuid.UUID(data["id"]))
        assert folder is not None

    def test_create_folder_nonexistent_collection_404(self, client):
        resp = client.post(
            "/api/v1/literature/collections/folders",
            json={"collection_id": str(uuid.uuid4()), "name": "x"},
        )
        assert resp.status_code == 404

    def test_create_folder_cross_user_denied(self, client, db_session, other_user, fake_client):
        created = _create_collection(client)
        other = _build_client(db_session, other_user, fake_client)
        resp = other.post(
            "/api/v1/literature/collections/folders",
            json={"collection_id": created["id"], "name": "x"},
        )
        app.dependency_overrides.clear()
        assert resp.status_code == 403


# --- Collection items (save / remove) --------------------------------------


class TestCollectionItems:
    def test_save_item_preserves_source(self, client, db_session):
        created = _create_collection(client)
        resp = client.post(
            f"/api/v1/literature/collections/{created['id']}/items",
            json={
                "title": "Blood Pressure Management",
                "authors": ["Smith J", "Doe A"],
                "journal": "The Lancet",
                "abstract": "abstract text",
                "doi": "10.1/x",
                "source": "PubMed",
                "external_id": "38000001",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # Authors list normalised to a joined string.
        assert data["authors"] == "Smith J; Doe A"
        # Source label preserved (normalised to lower id, Req 10.37).
        assert data["source"] == "pubmed"
        assert data["external_id"] == "38000001"

    def test_save_item_into_folder(self, client):
        created = _create_collection(client)
        folder = client.post(
            "/api/v1/literature/collections/folders",
            json={"collection_id": created["id"], "name": "f1"},
        ).json()
        resp = client.post(
            f"/api/v1/literature/collections/{created['id']}/items",
            json={"title": "T", "source": "cnki", "folder_id": folder["id"]},
        )
        assert resp.status_code == 201
        assert resp.json()["folder_id"] == folder["id"]

    def test_save_item_bad_folder_404(self, client):
        created = _create_collection(client)
        resp = client.post(
            f"/api/v1/literature/collections/{created['id']}/items",
            json={"title": "T", "source": "cnki", "folder_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    def test_save_item_nonexistent_collection_404(self, client):
        resp = client.post(
            f"/api/v1/literature/collections/{uuid.uuid4()}/items",
            json={"title": "T", "source": "cnki"},
        )
        assert resp.status_code == 404

    def test_remove_item(self, client, db_session):
        created = _create_collection(client)
        col_id = created["id"]
        item = client.post(
            f"/api/v1/literature/collections/{col_id}/items",
            json={"title": "T", "source": "pubmed"},
        ).json()
        resp = client.delete(
            f"/api/v1/literature/collections/{col_id}/items/{item['id']}"
        )
        assert resp.status_code == 204
        assert db_session.get(CollectedLiterature, uuid.UUID(item["id"])) is None

    def test_remove_nonexistent_item_404(self, client):
        created = _create_collection(client)
        resp = client.delete(
            f"/api/v1/literature/collections/{created['id']}/items/{uuid.uuid4()}"
        )
        assert resp.status_code == 404

    def test_list_collection_filter_by_source(self, client):
        created = _create_collection(client)
        col_id = created["id"]
        client.post(
            f"/api/v1/literature/collections/{col_id}/items",
            json={"title": "CNKI doc", "source": "cnki"},
        )
        client.post(
            f"/api/v1/literature/collections/{col_id}/items",
            json={"title": "PubMed doc", "source": "pubmed"},
        )
        resp = client.get("/api/v1/literature/collections?source=cnki")
        items = resp.json()["collections"][0]["items"]
        assert len(items) == 1
        assert items[0]["source"] == "cnki"

    def test_list_collection_search_by_title(self, client):
        created = _create_collection(client)
        col_id = created["id"]
        client.post(
            f"/api/v1/literature/collections/{col_id}/items",
            json={"title": "Hypertension study", "source": "pubmed"},
        )
        client.post(
            f"/api/v1/literature/collections/{col_id}/items",
            json={"title": "Diabetes study", "source": "pubmed"},
        )
        resp = client.get("/api/v1/literature/collections?q=hypertension")
        items = resp.json()["collections"][0]["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Hypertension study"

    def test_save_item_cross_user_denied(self, client, db_session, other_user, fake_client):
        created = _create_collection(client)
        other = _build_client(db_session, other_user, fake_client)
        resp = other.post(
            f"/api/v1/literature/collections/{created['id']}/items",
            json={"title": "T", "source": "cnki"},
        )
        app.dependency_overrides.clear()
        assert resp.status_code == 403
