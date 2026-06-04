"""Literature search, translation, and collection API routes.

Implements the 文献检索与翻译 ("Literature_Search_Module") endpoints. Search,
detail, abstract translation, and MeSH suggestion are backed by the 「医析」
Agent running on Bedrock AgentCore, which orchestrates the self-developed
``cnki-search`` MCP and the open-source ``pubmed-mcp-server`` (and uses Claude
directly for translation — no separate translation tool).

Search results are *ephemeral*: they come live from the MCP servers via the
Agent and are NOT persisted. Only literature collections are stored
(``LiteratureCollection`` / ``CollectionFolder`` / ``CollectedLiterature``).

All collection endpoints enforce per-user data isolation (Requirement 10.43) by
scoping every query to the authenticated user via the access-control helpers
(404 missing / 403 cross-user).

Because the Agent returns natural language interleaved with the MCP tools' JSON
output, the search/detail/MeSH handlers tolerantly parse literature data out of
the response: they prefer a structured payload carried on the ``AgentResponse``
(``to_dict()``), and otherwise scan the response text for embedded JSON blocks
using the shared :func:`app.agent.entrypoint._iter_json_candidates` helper,
falling back to an empty result for plain-text-only responses.

The :class:`AgentCoreClient` is provided through the shared
``get_agentcore_client`` dependency (imported from :mod:`app.api.v1.analysis`)
so tests can override it with a fake returning canned ``AgentResponse`` objects,
avoiding real AWS calls. Agent failures are surfaced as HTTP 502, consistent
with the other routers.

Requirements: 10.1-10.46
"""

import uuid as uuid_mod
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...agent.entrypoint import _iter_json_candidates, _response_to_text
from ...core.database import get_db
from ...middleware.access_control import get_resource_or_deny
from ...middleware.auth import get_current_user
from ...models.literature import CollectedLiterature, CollectionFolder, LiteratureCollection
from ...models.user import User
from ...schemas.literature import (
    SOURCE_LABELS,
    BilingualContentResponse,
    CollectedLiteratureResponse,
    CollectionListResponse,
    CollectionResponse,
    CreateCollectionRequest,
    CreateFolderRequest,
    FolderResponse,
    LiteratureRecord,
    MeshSuggestResponse,
    SaveLiteratureRequest,
    SearchRequest,
    SearchResponse,
    TranslateRequest,
)
from ...services.agentcore_client import AgentCoreClient, AgentResponse
from .analysis import get_agentcore_client

router = APIRouter(prefix="/literature", tags=["literature"])

# Valid data-source identifiers (Requirement 10.6).
_VALID_SOURCES = ("cnki", "pubmed")

# Keys under which the Agent / MCP output may carry literature record lists.
_LITERATURE_CONTAINER_KEYS = ("results", "records", "literature", "articles", "items")
# Keys that mark a dict as a single literature record.
_RECORD_HINT_KEYS = ("title", "abstract", "doi", "pmid", "external_id")


# ---------------------------------------------------------------------------
# Agent invocation
# ---------------------------------------------------------------------------
async def _invoke_agent(
    client: AgentCoreClient,
    prompt: str,
    user_id: uuid_mod.UUID,
    context: dict[str, Any],
) -> AgentResponse:
    """Invoke the Agent, translating failures into a 502 error.

    Mirrors the failure handling in ``analysis.py`` / ``chat.py`` / ``reports.py``:
    any exception from the AgentCore call is surfaced as HTTP 502 Bad Gateway.
    """
    payload = {
        "prompt": prompt,
        "user_id": str(user_id),
        "analysis_context": context,
    }
    try:
        return await client.invoke_agent(payload)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent invocation failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Response parsing helpers (tolerant; empty on plain text)
# ---------------------------------------------------------------------------
def _normalize_source(value: Any) -> str:
    """Normalise a raw data-source value to a canonical label ("CNKI"/"PubMed").

    Accepts the connector ``data_source`` strings ("CNKI", "PubMed"), the lower
    identifiers ("cnki", "pubmed"), and falls back to the original string when
    unrecognised.
    """
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered in SOURCE_LABELS:
        return SOURCE_LABELS[lowered]
    if text in SOURCE_LABELS.values():
        return text
    return text


def _coerce_authors(value: Any) -> list[str]:
    """Coerce an authors field into a list of name strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(a).strip() for a in value if str(a).strip()]
    text = str(value).strip()
    if not text:
        return []
    # Tolerate common separators used by the connectors.
    for sep in (";", ",", "、"):
        if sep in text:
            return [part.strip() for part in text.split(sep) if part.strip()]
    return [text]


def _coerce_keywords(value: Any) -> list[str]:
    """Coerce a keywords field into a list of strings (reuses author logic)."""
    return _coerce_authors(value)


def _record_from_dict(obj: dict) -> LiteratureRecord | None:
    """Build a :class:`LiteratureRecord` from a raw record dict.

    Returns ``None`` when ``obj`` does not look like a literature record (so
    non-record JSON blocks embedded in the response are skipped).
    """
    if not isinstance(obj, dict):
        return None
    if not any(key in obj for key in _RECORD_HINT_KEYS):
        return None

    abstract = obj.get("abstract")
    abstract = str(abstract) if abstract is not None else None
    # Abstract preview: first 200 characters (Requirement 10.22).
    preview = obj.get("abstract_preview")
    if preview is None and abstract is not None:
        preview = abstract[:200]

    pub_date = obj.get("publication_date") or obj.get("pub_date") or obj.get("date")
    external_id = obj.get("external_id") or obj.get("pmid") or obj.get("PMID")
    data_source = _normalize_source(obj.get("data_source") or obj.get("source"))

    citation = obj.get("citation_count")
    if citation is None:
        citation = obj.get("citations")
    try:
        citation = int(citation) if citation is not None else None
    except (TypeError, ValueError):
        citation = None

    return LiteratureRecord(
        title=str(obj.get("title") or ""),
        authors=_coerce_authors(obj.get("authors")),
        journal=(str(obj["journal"]) if obj.get("journal") is not None else None),
        publication_date=(str(pub_date) if pub_date is not None else None),
        abstract=abstract,
        abstract_preview=(str(preview) if preview is not None else None),
        keywords=_coerce_keywords(obj.get("keywords")),
        doi=(str(obj["doi"]) if obj.get("doi") is not None else None),
        data_source=data_source,
        external_id=(str(external_id) if external_id is not None else None),
        citation_count=citation,
    )


def _iter_record_dicts(value: Any) -> list[dict]:
    """Flatten a parsed JSON value into candidate record dicts.

    Expands explicit container objects (``{"results": [...]}`` etc.) and lists,
    yielding the leaf dicts to classify.
    """
    out: list[dict] = []
    if isinstance(value, list):
        for element in value:
            out.extend(_iter_record_dicts(element))
    elif isinstance(value, dict):
        expanded = False
        for key in _LITERATURE_CONTAINER_KEYS:
            container = value.get(key)
            if isinstance(container, list):
                expanded = True
                for item in container:
                    out.extend(_iter_record_dicts(item))
        if not expanded:
            out.append(value)
    return out


def _parse_records(response: AgentResponse) -> list[LiteratureRecord]:
    """Extract literature records from an Agent response (tolerant).

    Prefers a structured payload carried on the response dict (``results`` /
    ``records`` / ``literature`` keys via ``to_dict()`` extras), then scans the
    response text for embedded JSON blocks. Returns an empty list for plain
    text or when no record-shaped data is found.
    """
    records: list[LiteratureRecord] = []
    seen: set[tuple[str, str, str]] = set()

    def _consume(value: Any) -> None:
        for candidate in _iter_record_dicts(value):
            record = _record_from_dict(candidate)
            if record is None:
                continue
            key = (record.title, record.data_source, record.external_id or record.doi or "")
            if key in seen:
                continue
            seen.add(key)
            records.append(record)

    # 1) Structured payload carried directly on the response (test/fixture path
    #    and any runtime that pre-extracts records).
    payload = response.to_dict()
    for key in _LITERATURE_CONTAINER_KEYS:
        if isinstance(payload.get(key), list):
            _consume({key: payload[key]})

    # 2) Embedded JSON blocks in the natural-language response text.
    text = _response_to_text(response.response)
    for value in _iter_json_candidates(text):
        _consume(value)

    return records


def _apply_sort(records: list[LiteratureRecord], sort_by: str | None) -> list[LiteratureRecord]:
    """Sort merged records by the requested key (Requirement 10.24).

    ``date`` sorts by publication date (newest first); ``citations`` by citation
    count (highest first). ``relevance`` (the default) preserves the Agent's
    returned order. Sorts are stable so ties keep relevance order.
    """
    if sort_by == "date":
        return sorted(records, key=lambda r: r.publication_date or "", reverse=True)
    if sort_by == "citations":
        return sorted(records, key=lambda r: r.citation_count or 0, reverse=True)
    return records


def _source_totals(records: list[LiteratureRecord], sources: list[str]) -> dict[str, int]:
    """Compute the per-source result count keyed by label (Requirement 10.28)."""
    totals: dict[str, int] = {SOURCE_LABELS[s]: 0 for s in sources}
    for record in records:
        label = record.data_source
        totals[label] = totals.get(label, 0) + 1
    return totals


def _validate_sources(sources: list[str]) -> list[str]:
    """Validate and de-duplicate the requested data sources (Requirement 10.6)."""
    if not sources:
        return list(_VALID_SOURCES)
    normalized: list[str] = []
    for source in sources:
        key = str(source).strip().lower()
        if key not in _VALID_SOURCES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid data source '{source}'. Valid sources: cnki, pubmed.",
            )
        if key not in normalized:
            normalized.append(key)
    return normalized


def _detect_language(text: str) -> str:
    """Heuristically detect whether ``text`` is Chinese ("zh") or English ("en").

    Chinese is detected by the presence of CJK Unified Ideographs.
    """
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


# ---------------------------------------------------------------------------
# Search / detail / translate / MeSH
# ---------------------------------------------------------------------------
@router.post("/search", response_model=SearchResponse)
async def search_literature(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> SearchResponse:
    """Search medical literature across CNKI / PubMed / both.

    Validates the requested sources (subset of ``{cnki, pubmed}``, defaulting to
    both), instructs the Agent to search the selected sources in parallel with
    the supplied filters, parses the merged record list out of the Agent's
    response, applies the requested sort, paginates (default 20/page), and
    returns the page together with the merged total and per-source counts.

    An empty query (or a response with no records) still returns HTTP 200 with
    an empty result list (Requirement 10.27).
    Requirements: 10.2-10.8, 10.12, 10.13, 10.17-10.22, 10.24, 10.28
    """
    sources = _validate_sources(body.sources)
    source_labels = "、".join(SOURCE_LABELS[s] for s in sources)

    filters: list[str] = []
    if body.author:
        filters.append(f"作者：{body.author}")
    if body.journal:
        filters.append(f"期刊：{body.journal}")
    if body.date_from or body.date_to:
        filters.append(f"发表时间范围：{body.date_from or '不限'} 至 {body.date_to or '不限'}")
    if body.subject:
        filters.append(f"学科领域：{body.subject}")
    filter_text = ("；筛选条件：" + "；".join(filters)) if filters else ""

    prompt = (
        f"请在以下文献数据源中检索医学文献：{source_labels}。"
        f"检索关键词：「{body.keywords}」{filter_text}。"
        "若选择了多个数据源，请并行检索并合并结果。"
        "默认检索最近 5 年发表的文献。"
        "请以 JSON 数组形式返回文献记录列表，每条记录包含字段："
        "title、authors、journal、publication_date、abstract、keywords、doi、"
        "data_source（CNKI 或 PubMed）、external_id（PubMed 为 PMID）。"
    )
    context = {
        "keywords": body.keywords,
        "sources": sources,
        "filters": {
            "author": body.author,
            "journal": body.journal,
            "date_from": body.date_from,
            "date_to": body.date_to,
            "subject": body.subject,
        },
        "page": body.page,
        "page_size": body.page_size,
        "sort_by": body.sort_by,
    }

    agent_response = await _invoke_agent(client, prompt, current_user.id, context)

    records = _parse_records(agent_response)
    # Keep only records from the selected sources (defensive merge filter).
    selected_labels = {SOURCE_LABELS[s] for s in sources}
    records = [r for r in records if r.data_source in selected_labels]

    records = _apply_sort(records, body.sort_by)
    totals = _source_totals(records, sources)

    total = len(records)
    start = (body.page - 1) * body.page_size
    end = start + body.page_size
    page_records = records[start:end]

    return SearchResponse(
        results=page_records,
        page=body.page,
        page_size=body.page_size,
        total=total,
        totals=totals,
    )


@router.get("/mesh/suggest", response_model=MeshSuggestResponse)
async def suggest_mesh_terms(
    q: str = Query("", description="用于建议 MeSH 术语的检索关键词"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> MeshSuggestResponse:
    """Suggest relevant MeSH terms for a PubMed query (Requirement 10.20).

    Invokes the Agent (which drives ``pubmed-mcp-server``'s ``search_by_mesh``)
    to recommend MeSH terms for ``q``. The response is tolerantly parsed: a
    ``terms``/``mesh_terms`` JSON array, a bare JSON array of strings, or an
    empty list when none are found.
    """
    prompt = (
        f"请通过 pubmed-mcp-server 的 MeSH 工具，为检索关键词「{q}」推荐相关的 MeSH 标准术语。"
        '请以 JSON 形式返回，例如 {"terms": ["Diabetes Mellitus", "Hypertension"]}。'
    )
    agent_response = await _invoke_agent(client, prompt, current_user.id, {"query": q})

    terms = _parse_mesh_terms(agent_response)
    return MeshSuggestResponse(terms=terms)


def _parse_mesh_terms(response: AgentResponse) -> list[str]:
    """Extract suggested MeSH terms from an Agent response (tolerant)."""
    terms: list[str] = []
    seen: set[str] = set()

    def _add(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text and text not in seen:
                seen.add(text)
                terms.append(text)

    def _consume(value: Any) -> None:
        if isinstance(value, dict):
            for key in ("terms", "mesh_terms", "suggestions"):
                container = value.get(key)
                if isinstance(container, list):
                    for item in container:
                        _add(item)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    _add(item)
                else:
                    _consume(item)

    payload = response.to_dict()
    for key in ("terms", "mesh_terms", "suggestions"):
        if isinstance(payload.get(key), list):
            _consume({key: payload[key]})

    text = _response_to_text(response.response)
    for value in _iter_json_candidates(text):
        _consume(value)

    return terms


# ---------------------------------------------------------------------------
# Collections CRUD (user-scoped)
# ---------------------------------------------------------------------------
def _get_collection_or_deny(
    db: Session, collection_id: uuid_mod.UUID, user_id: uuid_mod.UUID
) -> LiteratureCollection:
    """Load a collection enforcing ownership (404 missing / 403 cross-user).

    Requirement 10.43 — collection access is restricted to the owning user.
    """
    return get_resource_or_deny(db, LiteratureCollection, collection_id, user_id, "collection")


@router.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
def create_collection(
    body: CreateCollectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionResponse:
    """Create a literature collection for the user (Requirement 10.36)."""
    collection = LiteratureCollection(user_id=current_user.id, name=body.name)
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return CollectionResponse.model_validate(collection)


@router.get("/collections", response_model=CollectionListResponse)
def list_collections(
    source: str | None = Query(None, description="按数据源过滤收藏项：cnki 或 pubmed"),
    q: str | None = Query(None, description="在收藏项标题/关键词中搜索"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionListResponse:
    """List the user's literature collections, newest first (Requirement 10.38).

    Optionally filters the saved items within each collection by data source
    (Requirement 10.40) and/or a title/keyword search term (Requirement 10.42).
    Collections are always scoped to the authenticated user (Requirement 10.43).
    """
    collections = db.execute(
        select(LiteratureCollection)
        .where(LiteratureCollection.user_id == current_user.id)
        .order_by(LiteratureCollection.created_at.desc())
    ).scalars().all()

    source_key = str(source).strip().lower() if source else None
    query_text = q.strip().lower() if q else None

    responses: list[CollectionResponse] = []
    for collection in collections:
        # Items sorted by collection date descending (Requirement 10.38).
        items = sorted(collection.items, key=lambda i: i.created_at, reverse=True)
        if source_key:
            items = [i for i in items if str(i.source).strip().lower() == source_key]
        if query_text:
            items = [
                i
                for i in items
                if query_text in (i.title or "").lower()
                or query_text in (i.abstract or "").lower()
            ]
        response = CollectionResponse(
            id=collection.id,
            name=collection.name,
            created_at=collection.created_at,
            folders=[FolderResponse.model_validate(f) for f in collection.folders],
            items=[CollectedLiteratureResponse.model_validate(i) for i in items],
        )
        responses.append(response)

    return CollectionListResponse(collections=responses, total=len(responses))


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a collection and its folders/items (cascade) (Requirement 10.41).

    Ownership-scoped: 404 if missing, 403 if another user's (Requirement 10.43).
    """
    collection = _get_collection_or_deny(db, collection_id, current_user.id)
    db.delete(collection)
    db.commit()


@router.post(
    "/collections/folders",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_folder(
    body: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FolderResponse:
    """Create a custom folder under a user-owned collection (Requirement 10.39).

    The parent collection must belong to the user (404/403 otherwise).
    """
    collection = _get_collection_or_deny(db, body.collection_id, current_user.id)
    folder = CollectionFolder(collection_id=collection.id, name=body.name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return FolderResponse.model_validate(folder)


@router.post(
    "/collections/{collection_id}/items",
    response_model=CollectedLiteratureResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_literature(
    collection_id: uuid_mod.UUID,
    body: SaveLiteratureRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectedLiteratureResponse:
    """Save a literature record into a collection (Requirements 10.36, 10.37).

    The collection must belong to the user (404/403). When ``folder_id`` is
    given it must belong to the same collection (else 404). The data-source
    label is preserved with the saved record (Requirement 10.37).
    """
    collection = _get_collection_or_deny(db, collection_id, current_user.id)

    folder_id: uuid_mod.UUID | None = None
    if body.folder_id is not None:
        folder = db.execute(
            select(CollectionFolder).where(
                CollectionFolder.id == body.folder_id,
                CollectionFolder.collection_id == collection.id,
            )
        ).scalar_one_or_none()
        if folder is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="folder not found",
            )
        folder_id = folder.id

    item = CollectedLiterature(
        collection_id=collection.id,
        folder_id=folder_id,
        title=body.title,
        authors=body.authors,
        journal=body.journal,
        publication_date=body.publication_date,
        abstract=body.abstract,
        doi=body.doi,
        source=str(body.source).strip().lower() if body.source else body.source,
        external_id=body.external_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return CollectedLiteratureResponse.model_validate(item)


@router.delete(
    "/collections/{collection_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_literature(
    collection_id: uuid_mod.UUID,
    item_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove a saved literature item from a collection (Requirement 10.41).

    The collection must belong to the user (404/403); the item must belong to
    the collection (else 404).
    """
    collection = _get_collection_or_deny(db, collection_id, current_user.id)

    item = db.execute(
        select(CollectedLiterature).where(
            CollectedLiterature.id == item_id,
            CollectedLiterature.collection_id == collection.id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="literature item not found",
        )

    db.delete(item)
    db.commit()


# ---------------------------------------------------------------------------
# Detail / translate (dynamic id routes — declared last so the static
# ``/collections`` and ``/mesh/suggest`` routes take precedence in matching)
# ---------------------------------------------------------------------------
@router.get("/{literature_id}", response_model=LiteratureRecord)
async def get_literature_detail(
    literature_id: str,
    source: str = Query(..., description="数据源：cnki 或 pubmed"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> LiteratureRecord:
    """Get the full detail of a literature record (Requirement 10.26).

    Since search results are not persisted, ``{literature_id}`` is the external
    id (PMID for PubMed, the CNKI id for CNKI) and the ``source`` query param is
    required. The Agent fetches the detail (``get_article_details`` for PubMed /
    the CNKI detail tool for CNKI). A 404 is returned when no record is found.
    """
    sources = _validate_sources([source])
    label = SOURCE_LABELS[sources[0]]

    prompt = (
        f"请从数据源 {label} 获取文献（标识 {literature_id}）的完整详情，"
        "包括完整摘要、全部作者、期刊、发表时间、关键词、DOI 和数据来源标识。"
        "请以 JSON 对象形式返回，字段包括 title、authors、journal、publication_date、"
        "abstract、keywords、doi、data_source、external_id。"
    )
    context = {"literature_id": literature_id, "source": sources[0]}

    agent_response = await _invoke_agent(client, prompt, current_user.id, context)

    records = _parse_records(agent_response)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="literature not found",
        )
    return records[0]


@router.post("/{literature_id}/translate", response_model=BilingualContentResponse)
async def translate_literature(
    literature_id: str,
    body: TranslateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> BilingualContentResponse:
    """Translate a literature record's title + abstract for the Bilingual_View.

    The content is supplied in the request body (search results are ephemeral).
    The source language is resolved from ``source_language``, else ``source``
    (cnki ⇒ zh, pubmed ⇒ en), else auto-detected from the text; the target is
    the opposite language. The Agent (Claude directly) performs the translation
    and returns both versions side by side. Agent failure → 502 (Req 10.35).
    Requirements: 10.29-10.34
    """
    # Resolve the source language.
    if body.source_language in ("zh", "en"):
        source_language = body.source_language
    elif body.source and str(body.source).strip().lower() == "cnki":
        source_language = "zh"
    elif body.source and str(body.source).strip().lower() == "pubmed":
        source_language = "en"
    else:
        source_language = _detect_language(f"{body.title or ''} {body.abstract or ''}")
    target_language = "en" if source_language == "zh" else "zh"

    lang_label = {"zh": "中文", "en": "英文"}
    prompt = (
        f"请将以下文献的标题和摘要从{lang_label[source_language]}翻译为"
        f"{lang_label[target_language]}，保持医学术语准确。"
        f"\n标题：{body.title or ''}\n摘要：{body.abstract or ''}\n"
        "请以 JSON 对象形式返回，字段包括 translated_title、translated_abstract。"
    )
    context = {
        "literature_id": literature_id,
        "source_language": source_language,
        "target_language": target_language,
    }

    agent_response = await _invoke_agent(client, prompt, current_user.id, context)

    translated_title, translated_abstract = _parse_translation(agent_response)

    return BilingualContentResponse(
        original_title=body.title,
        translated_title=translated_title,
        original_abstract=body.abstract,
        translated_abstract=translated_abstract,
        source_language=source_language,
        target_language=target_language,
    )


def _parse_translation(response: AgentResponse) -> tuple[str | None, str | None]:
    """Extract the translated title/abstract from an Agent response (tolerant).

    Looks for a JSON object carrying ``translated_title`` / ``translated_abstract``
    (or ``title`` / ``abstract``) on the response payload or embedded in the
    response text. Falls back to the plain response text as the translated
    abstract when no structured payload is present.
    """

    def _from_obj(obj: dict) -> tuple[str | None, str | None]:
        title = obj.get("translated_title")
        if title is None:
            title = obj.get("title")
        abstract = obj.get("translated_abstract")
        if abstract is None:
            abstract = obj.get("abstract")
        title = str(title) if title is not None else None
        abstract = str(abstract) if abstract is not None else None
        return title, abstract

    payload = response.to_dict()
    if any(k in payload for k in ("translated_title", "translated_abstract")):
        return _from_obj(payload)

    text = _response_to_text(response.response)
    for value in _iter_json_candidates(text):
        for candidate in value if isinstance(value, list) else [value]:
            if isinstance(candidate, dict) and any(
                k in candidate for k in ("translated_title", "translated_abstract", "title", "abstract")
            ):
                return _from_obj(candidate)

    # No structured payload — treat the whole response text as the translation.
    stripped = text.strip()
    return None, (stripped or None)
