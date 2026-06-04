"""PDF literature upload and translation API routes.

Implements the PDF 文献上传与翻译 ("PDF translation") endpoints (Requirement 11).
A dedicated PDF upload entry (separate from the data upload of Requirement 1)
stores the file to S3 and records it; translation is driven by the 「医析」 Agent
running on Bedrock AgentCore, which orchestrates the open-source MarkItDown MCP
to parse the PDF structure and uses Claude directly for full-document,
paragraph-level translation (no separate translation MCP).

Endpoints
---------
* ``POST /upload`` — upload a PDF (``.pdf`` only, ≤ 50MB), store to S3, create a
  :class:`TranslationRecord`.
* ``POST /{translation_id}/translate`` — invoke the Agent to parse + translate
  the document, persisting a :class:`TranslationResult` (paragraph arrays +
  document structure) and updating the record's languages / progress / status.
* ``GET /{translation_id}/status`` — translation progress + detected languages.
* ``GET /{translation_id}/result`` — the bilingual Translation_Result.
* ``GET /{translation_id}/download`` — presigned S3 URL for the exported
  document (``format`` = pdf/docx, ``mode`` = bilingual/translation).
* ``GET /history`` — the user's translation history (newest first).
* ``DELETE /{translation_id}`` — delete a record (cascades to its result).

All ownership-scoped endpoints enforce per-user data isolation (Requirements
11.9, 11.50) via :func:`get_resource_or_deny` (404 missing / 403 cross-user).

Because the Agent returns natural language interleaved with the MarkItDown /
Claude JSON output, the translate handler tolerantly parses the Translation_Result
out of the response: it prefers a structured payload carried on the
``AgentResponse`` (``to_dict()``), and otherwise scans the response text for
embedded JSON blocks via the shared
:func:`app.agent.entrypoint._iter_json_candidates` helper.

The :class:`AgentCoreClient` is provided through the shared
``get_agentcore_client`` dependency (imported from :mod:`app.api.v1.analysis`)
so tests can override it with a fake returning canned ``AgentResponse`` objects.
Agent failures are surfaced as HTTP 502, consistent with the other routers. S3
access goes through the module-level :mod:`app.services.s3_client` functions so
tests can monkeypatch them.

Requirements: 11.1-11.50
"""

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...agent.entrypoint import _iter_json_candidates, _response_to_text
from ...core.database import get_db
from ...middleware.access_control import get_resource_or_deny
from ...middleware.auth import get_current_user
from ...models.translation import TranslationRecord, TranslationResult
from ...models.user import User
from ...schemas.translation import (
    TranslateRequest,
    TranslationDownloadResponse,
    TranslationHistoryItem,
    TranslationHistoryResponse,
    TranslationResultResponse,
    TranslationStatusResponse,
    TranslationUploadResponse,
)
from ...services import s3_client
from ...services.agentcore_client import AgentCoreClient, AgentResponse
from .analysis import get_agentcore_client

router = APIRouter(prefix="/translation", tags=["translation"])

# Only PDF files are accepted for translation (Requirement 11.2).
ALLOWED_EXTENSION = ".pdf"
# Maximum PDF size: 50MB (Requirement 11.3).
MAX_PDF_SIZE = 50 * 1024 * 1024

# Supported export formats mapped to the TranslationResult S3-key attribute
# (Requirements 11.38, 11.39).
_FORMAT_KEY_ATTR: dict[str, str] = {
    "pdf": "s3_key_pdf",
    "docx": "s3_key_docx",
}
# Supported download content modes (Requirement 11.41).
_VALID_MODES = ("bilingual", "translation")

# Human-readable language labels for prompts.
_LANG_LABEL = {"zh": "中文", "en": "英文"}


def _now() -> datetime:
    """Return a timezone-aware current timestamp."""
    return datetime.now(timezone.utc)


def _get_file_extension(filename: str) -> str:
    """Extract the lowercase file extension (including the dot) from a filename."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


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

    Mirrors the failure handling in the other routers: any exception from the
    AgentCore call is surfaced as HTTP 502 Bad Gateway.
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
# Response parsing helpers (tolerant)
# ---------------------------------------------------------------------------
# Keys that mark a parsed JSON dict as a Translation_Result payload.
_RESULT_HINT_KEYS = ("original_paragraphs", "translated_paragraphs")


def _coerce_paragraphs(value: Any) -> list[str]:
    """Coerce a paragraphs field into a list of strings.

    Accepts a list (each element stringified) or a single string. Returns an
    empty list for ``None`` / unrecognised shapes.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value] if value else []
    return []


def _extract_s3_keys(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract exported PDF / Word S3 keys from a translation payload.

    The Agent may surface the exported document keys under a few shapes:

    * ``payload["s3_key_pdf"]`` / ``payload["s3_key_docx"]`` (explicit keys)
    * ``payload["exports"]`` as a list of ``{"format": "pdf"|"docx",
      "s3_key": ...}`` entries
    * ``payload["exports"]`` as a mapping ``{"pdf": {"s3_key": ...}, ...}``

    Returns a ``(s3_key_pdf, s3_key_docx)`` tuple with ``None`` for any format
    that was not exported.
    """
    s3_key_pdf = payload.get("s3_key_pdf")
    s3_key_docx = payload.get("s3_key_docx")

    exports = payload.get("exports")
    if isinstance(exports, list):
        for entry in exports:
            if not isinstance(entry, dict):
                continue
            fmt = str(entry.get("format") or "").lower()
            key = entry.get("s3_key")
            if fmt == "pdf" and s3_key_pdf is None:
                s3_key_pdf = key
            elif fmt == "docx" and s3_key_docx is None:
                s3_key_docx = key
    elif isinstance(exports, dict):
        if s3_key_pdf is None and isinstance(exports.get("pdf"), dict):
            s3_key_pdf = exports["pdf"].get("s3_key")
        if s3_key_docx is None and isinstance(exports.get("docx"), dict):
            s3_key_docx = exports["docx"].get("s3_key")

    pdf = str(s3_key_pdf) if isinstance(s3_key_pdf, str) and s3_key_pdf else None
    docx = str(s3_key_docx) if isinstance(s3_key_docx, str) and s3_key_docx else None
    return pdf, docx


def _find_translation_payload(response: AgentResponse) -> dict | None:
    """Locate the Translation_Result payload in an Agent response (tolerant).

    Prefers a structured payload carried directly on the response dict (via
    ``to_dict()`` extras), then scans the response text for embedded JSON blocks,
    returning the first dict that looks like a Translation_Result (carries an
    ``original_paragraphs`` or ``translated_paragraphs`` key). Returns ``None``
    when no such payload is found.
    """
    payload = response.to_dict()
    if any(key in payload and payload[key] is not None for key in _RESULT_HINT_KEYS):
        return payload

    text = _response_to_text(response.response)
    for value in _iter_json_candidates(text):
        if isinstance(value, dict) and any(key in value for key in _RESULT_HINT_KEYS):
            return value
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and any(key in item for key in _RESULT_HINT_KEYS):
                    return item
    return None


def _result_response(record: TranslationRecord, result: TranslationResult) -> TranslationResultResponse:
    """Build a :class:`TranslationResultResponse` from a record + its result."""
    return TranslationResultResponse(
        id=result.id,
        translation_id=record.id,
        source_language=record.source_language,
        target_language=record.target_language,
        status=record.status,
        original_paragraphs=result.original_paragraphs,
        translated_paragraphs=result.translated_paragraphs,
        document_structure=result.document_structure,
    )


def _get_record_or_deny(
    db: Session, translation_id: uuid_mod.UUID, user_id: uuid_mod.UUID
) -> TranslationRecord:
    """Load a translation record enforcing ownership (404 missing / 403 cross-user).

    Requirements 11.9 / 11.50 — translation records are restricted to the owning
    user.
    """
    return get_resource_or_deny(
        db, TranslationRecord, translation_id, user_id, "translation record"
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=TranslationUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationUploadResponse:
    """Upload a PDF literature file for translation.

    Validates the file is a PDF (Requirement 11.2/11.5) and ≤ 50MB
    (Requirement 11.3/11.6), uploads it to S3, and creates a
    :class:`TranslationRecord` associated with the authenticated user
    (Requirement 11.9). The page count is determined later during parsing and is
    left ``None`` here.
    Requirements: 11.1-11.7, 11.9
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename is required",
        )

    ext = _get_file_extension(file.filename)
    if ext != ALLOWED_EXTENSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted (.pdf extension)",
        )

    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is empty",
        )

    if file_size > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File size exceeds maximum limit of {MAX_PDF_SIZE // (1024 * 1024)}MB",
        )

    # Generate a unique stored filename and S3 key scoped to the user.
    file_uuid = uuid_mod.uuid4()
    original_filename = file.filename
    stored_filename = f"{file_uuid}_{original_filename}"
    s3_key = f"translations/{current_user.id}/{stored_filename}"

    try:
        s3_client.upload_file(s3_key, content, file.content_type or "application/pdf")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {exc}",
        ) from exc

    record = TranslationRecord(
        user_id=current_user.id,
        filename=stored_filename,
        original_filename=original_filename,
        file_size=file_size,
        s3_key=s3_key,
        status="uploaded",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return TranslationUploadResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Translate trigger
# ---------------------------------------------------------------------------
@router.post("/{translation_id}/translate", response_model=TranslationResultResponse)
async def translate_pdf(
    translation_id: uuid_mod.UUID,
    body: TranslateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AgentCoreClient = Depends(get_agentcore_client),
) -> TranslationResultResponse:
    """Trigger full-document translation of an uploaded PDF (Requirement 11.21).

    Invokes the Agent — which drives the MarkItDown MCP to parse the PDF text +
    structure (Requirements 11.10-11.15) and uses Claude directly for
    paragraph-level translation preserving structure and medical terminology
    (Requirements 11.22-11.27) — then persists a :class:`TranslationResult` with
    the original / translated paragraph arrays and document structure, and
    updates the record's source / target languages, progress, status, and
    completion time.

    An optional ``source_language`` override (``zh`` / ``en``) takes precedence
    over the Agent's detection (Requirement 11.19). On Agent failure the record
    status is set to ``failed`` and a 502 is returned (Requirement 11.29).
    Requirements: 11.16-11.29
    """
    record = _get_record_or_deny(db, translation_id, current_user.id)
    override = (body.source_language if body else None)
    override = override.strip().lower() if isinstance(override, str) else None
    if override is not None and override not in ("zh", "en"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_language must be 'zh' or 'en'",
        )

    # Mark as processing for the duration of the (synchronous) invocation.
    record.status = "processing"
    record.progress = 0.0
    db.commit()

    override_hint = (
        f"用户已手动指定源语言为{_LANG_LABEL[override]}，请按此语言翻译。"
        if override
        else "请自动检测文档主要语言（中文或英文）。"
    )
    prompt = (
        f"请翻译已上传的 PDF 文献「{record.original_filename}」"
        f"（S3 路径 {record.s3_key}）。"
        "请先使用 MarkItDown 解析 PDF，提取正文文本并识别文档结构"
        "（标题、章节标题、段落、图表说明、参考文献），保持阅读顺序。"
        f"{override_hint}"
        "检测语言后进行全文段落级翻译：英文文档翻译为中文，中文文档翻译为英文，"
        "保持每个原文段落与译文段落一一对应，保留文档结构，医学术语使用目标语言的标准译法。"
        "请以 JSON 对象形式返回，字段包括："
        "source_language（zh 或 en）、target_language、page_count、"
        "original_paragraphs（原文段落字符串数组）、"
        "translated_paragraphs（译文段落字符串数组，与原文一一对应）、"
        "document_structure（文档结构对象）。"
    )
    context = {
        "translation_id": str(record.id),
        "s3_key": record.s3_key,
        "filename": record.original_filename,
        "source_language_override": override,
    }

    try:
        agent_response = await _invoke_agent(client, prompt, current_user.id, context)
    except HTTPException:
        record.status = "failed"
        db.commit()
        raise

    payload = _find_translation_payload(agent_response)
    if payload is None:
        record.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent did not return a parseable translation result",
        )

    # Resolve the source language: override wins, else the payload's detected
    # language, else default to English. The target is always the opposite
    # language (Requirements 11.22, 11.23).
    source_language = override or payload.get("source_language") or "en"
    source_language = str(source_language).strip().lower()
    if source_language not in ("zh", "en"):
        source_language = "en"
    target_language = "zh" if source_language == "en" else "en"

    original_paragraphs = _coerce_paragraphs(payload.get("original_paragraphs"))
    translated_paragraphs = _coerce_paragraphs(payload.get("translated_paragraphs"))
    document_structure = payload.get("document_structure")
    if not isinstance(document_structure, dict):
        document_structure = None
    s3_key_pdf, s3_key_docx = _extract_s3_keys(payload)

    page_count = payload.get("page_count")
    try:
        page_count = int(page_count) if page_count is not None else None
    except (TypeError, ValueError):
        page_count = None

    # Replace any prior result (the model enforces a unique translation_id).
    existing = db.execute(
        select(TranslationResult).where(TranslationResult.translation_id == record.id)
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.flush()

    result = TranslationResult(
        translation_id=record.id,
        original_paragraphs=original_paragraphs,
        translated_paragraphs=translated_paragraphs,
        document_structure=document_structure,
        s3_key_pdf=s3_key_pdf,
        s3_key_docx=s3_key_docx,
    )
    db.add(result)

    record.source_language = source_language
    record.target_language = target_language
    if page_count is not None:
        record.page_count = page_count
    record.status = "completed"
    record.progress = 100.0
    record.completed_at = _now()

    db.commit()
    db.refresh(record)
    db.refresh(result)

    return _result_response(record, result)


# ---------------------------------------------------------------------------
# Status / result
# ---------------------------------------------------------------------------
@router.get("/history", response_model=TranslationHistoryResponse)
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationHistoryResponse:
    """List the user's translation history, newest first (Requirements 11.43, 11.44).

    Scoped to the authenticated user (Requirement 11.50).
    """
    records = db.execute(
        select(TranslationRecord)
        .where(TranslationRecord.user_id == current_user.id)
        .order_by(TranslationRecord.created_at.desc())
    ).scalars().all()

    return TranslationHistoryResponse(
        records=[TranslationHistoryItem.model_validate(r) for r in records],
        total=len(records),
    )


@router.get("/{translation_id}/status", response_model=TranslationStatusResponse)
def get_status(
    translation_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationStatusResponse:
    """Query translation progress + detected languages (Requirements 11.19, 11.28)."""
    record = _get_record_or_deny(db, translation_id, current_user.id)
    return TranslationStatusResponse.model_validate(record)


@router.get("/{translation_id}/result", response_model=TranslationResultResponse)
def get_result(
    translation_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationResultResponse:
    """Get the bilingual Translation_Result for a record (Req 11.24, 11.30-11.34).

    Returns 404 when the document has not yet been translated.
    """
    record = _get_record_or_deny(db, translation_id, current_user.id)
    result = db.execute(
        select(TranslationResult).where(TranslationResult.translation_id == record.id)
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="translation result not available; the document has not been translated yet",
        )
    return _result_response(record, result)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
@router.get("/{translation_id}/download", response_model=TranslationDownloadResponse)
def download_translation(
    translation_id: uuid_mod.UUID,
    format: str = Query("pdf", description="下载格式：pdf 或 docx"),
    mode: str = Query("bilingual", description="内容模式：bilingual（双语）或 translation（仅翻译）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationDownloadResponse:
    """Return a presigned S3 URL for downloading the exported translation document.

    The record must belong to the authenticated user (404 missing / 403
    cross-user). ``format`` selects PDF (default) or Word (Requirements 11.38,
    11.39); ``mode`` selects bilingual (default) or translated-only content
    (Requirement 11.41). An unsupported ``format`` / ``mode`` yields 400; a
    missing exported file yields 404.

    Note: the :class:`TranslationResult` tracks a single S3 key per format
    (``s3_key_pdf`` / ``s3_key_docx``) rather than a per-mode key, so the stored
    key for the requested format is treated as the exportable document and the
    requested ``mode`` is echoed back in the response.
    Requirements: 11.37-11.41
    """
    normalized_format = format.lower()
    key_attr = _FORMAT_KEY_ATTR.get(normalized_format)
    if key_attr is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{format}'. Supported formats: pdf, docx.",
        )

    normalized_mode = mode.lower()
    if normalized_mode not in _VALID_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported mode '{mode}'. Supported modes: bilingual, translation.",
        )

    record = _get_record_or_deny(db, translation_id, current_user.id)
    result = db.execute(
        select(TranslationResult).where(TranslationResult.translation_id == record.id)
    ).scalar_one_or_none()

    s3_key = getattr(result, key_attr) if result is not None else None
    if not s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translation is not available for download in '{normalized_format}' format.",
        )

    download_url = s3_client.get_presigned_url(s3_key)
    return TranslationDownloadResponse(
        download_url=download_url,
        format=normalized_format,
        mode=normalized_mode,
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@router.delete("/{translation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_translation(
    translation_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a translation record and its associated result + PDF (Req 11.46, 11.47).

    Ownership-scoped (404 missing / 403 cross-user, Requirement 11.50). The
    TranslationRecord cascades deletion to its TranslationResult
    (``cascade="all, delete-orphan"``); the stored PDF object is best-effort
    removed from S3.
    """
    record = _get_record_or_deny(db, translation_id, current_user.id)

    # Best-effort S3 cleanup of the uploaded PDF (and any exported files).
    s3_keys: list[str] = [record.s3_key]
    if record.result is not None:
        for key in (record.result.s3_key_pdf, record.result.s3_key_docx):
            if key:
                s3_keys.append(key)
    for key in s3_keys:
        try:
            s3_client.delete_file(key)
        except Exception:  # noqa: BLE001 - cleanup is best-effort
            pass

    db.delete(record)
    db.commit()
