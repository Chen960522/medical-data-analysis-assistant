"""Data file upload and management API routes.

Implements file upload, listing, preview, quality report, and deletion.
Requirements: 1.1-1.7, 2.1-2.6
"""

import uuid as uuid_mod
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...middleware.auth import get_current_user
from ...models.data import DataFile
from ...models.user import User
from ...schemas.data import (
    ColumnQuality,
    DataFileListResponse,
    DataFileResponse,
    DataPreviewResponse,
    DataQualityResponse,
    UploadResponse,
)
from ...services import s3_client
from ...services.data_parser import parse_file, detect_column_types, detect_missing_values

router = APIRouter(prefix="/data", tags=["data"])

# Allowed file extensions and MIME types
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/json",
    "application/octet-stream",  # fallback for some clients
}
MAX_FILE_SIZE = settings.s3_max_file_size  # 100MB


def _get_file_extension(filename: str) -> str:
    """Extract lowercase file extension from filename."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _validate_file(file: UploadFile) -> str:
    """Validate file format and return the extension.

    Raises HTTPException if validation fails.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename is required",
        )

    ext = _get_file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file format. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Secondary MIME type check (lenient - some clients send generic types)
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        # Allow if extension is valid but MIME is unexpected
        pass

    return ext


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Upload a data file.

    Validates file format and size, uploads to S3, and creates a DataFile record.
    Requirements: 1.1-1.6
    """
    # Validate file format
    ext = _validate_file(file)

    # Read file content and validate size
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is empty",
        )

    # Generate unique filename and S3 key
    file_uuid = uuid_mod.uuid4()
    original_filename = file.filename or "unknown"
    stored_filename = f"{file_uuid}_{original_filename}"
    s3_key = f"data/{current_user.id}/{stored_filename}"

    # Upload to S3
    try:
        s3_client.upload_file(s3_key, content, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {str(e)}",
        )

    # Parse file to get row/column counts using the data_parser service
    row_count = None
    column_count = None
    try:
        result = parse_file(content, ext)
        row_count = result.total_rows
        column_count = result.total_columns
    except Exception:
        # Parsing failure is non-fatal for upload
        pass

    # Create DataFile record
    data_file = DataFile(
        user_id=current_user.id,
        filename=stored_filename,
        original_filename=original_filename,
        file_size=file_size,
        file_format=ext.lstrip("."),
        s3_key=s3_key,
        row_count=row_count,
        column_count=column_count,
        status="uploaded",
    )
    db.add(data_file)
    db.commit()
    db.refresh(data_file)

    return UploadResponse(
        message=f"File '{original_filename}' uploaded successfully",
        file=DataFileResponse.model_validate(data_file),
    )


@router.get("/files", response_model=DataFileListResponse)
def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataFileListResponse:
    """Get current user's file list.

    Requirements: 8.18, 8.22
    """
    stmt = (
        select(DataFile)
        .where(DataFile.user_id == current_user.id)
        .order_by(DataFile.created_at.desc())
    )
    files = db.execute(stmt).scalars().all()

    return DataFileListResponse(
        files=[DataFileResponse.model_validate(f) for f in files],
        total=len(files),
    )


@router.get("/files/{file_id}/preview", response_model=DataPreviewResponse)
def get_file_preview(
    file_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataPreviewResponse:
    """Get data preview (first 10 rows) for a file.

    Requirements: 2.2
    """
    # Fetch file record with user isolation
    data_file = db.execute(
        select(DataFile).where(DataFile.id == file_id, DataFile.user_id == current_user.id)
    ).scalar_one_or_none()

    if data_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Download file from S3 and parse
    try:
        content = s3_client.get_file_content(data_file.s3_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file from storage",
        )

    try:
        result = parse_file(content, data_file.file_format)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {str(e)}",
        )

    # Return first 10 rows
    preview_rows = result.rows[:10]
    # Ensure all values are JSON-serializable
    serializable_rows = []
    for row in preview_rows:
        serializable_rows.append({k: _make_serializable(v) for k, v in row.items()})

    return DataPreviewResponse(
        file_id=data_file.id,
        filename=data_file.original_filename,
        columns=result.columns,
        rows=serializable_rows,
        total_rows=result.total_rows,
        total_columns=result.total_columns,
    )


@router.get("/files/{file_id}/quality", response_model=DataQualityResponse)
def get_file_quality(
    file_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataQualityResponse:
    """Get data quality report for a file.

    Returns total rows, columns, missing value percentage, and detected data types.
    Requirements: 2.4, 2.6
    """
    # Fetch file record with user isolation
    data_file = db.execute(
        select(DataFile).where(DataFile.id == file_id, DataFile.user_id == current_user.id)
    ).scalar_one_or_none()

    if data_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Download file from S3 and parse
    try:
        content = s3_client.get_file_content(data_file.s3_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file from storage",
        )

    try:
        result = parse_file(content, data_file.file_format)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {str(e)}",
        )

    if result.total_rows == 0 or not result.columns:
        return DataQualityResponse(
            file_id=data_file.id,
            filename=data_file.original_filename,
            total_rows=0,
            total_columns=0,
            missing_value_percentage=0.0,
            columns=[],
        )

    # Use data_parser service for type detection and missing value analysis
    col_types = detect_column_types(result.columns, result.rows)
    missing_report = detect_missing_values(result.columns, result.rows)

    column_quality = []
    for col in result.columns:
        missing_count = missing_report.per_column.get(col, 0)
        missing_pct = (missing_count / result.total_rows * 100) if result.total_rows > 0 else 0.0

        column_quality.append(
            ColumnQuality(
                name=col,
                dtype=col_types.get(col, "text"),
                missing_count=missing_count,
                missing_percentage=round(missing_pct, 2),
            )
        )

    return DataQualityResponse(
        file_id=data_file.id,
        filename=data_file.original_filename,
        total_rows=result.total_rows,
        total_columns=result.total_columns,
        missing_value_percentage=missing_report.overall_percentage,
        columns=column_quality,
    )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: uuid_mod.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a file and its S3 object.

    Requirements: 7.5, 8.20
    """
    # Fetch file record with user isolation
    data_file = db.execute(
        select(DataFile).where(DataFile.id == file_id, DataFile.user_id == current_user.id)
    ).scalar_one_or_none()

    if data_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Delete from S3
    try:
        s3_client.delete_file(data_file.s3_key)
    except Exception:
        # Log but don't fail - the DB record should still be cleaned up
        pass

    # Delete from database
    db.delete(data_file)
    db.commit()


def _make_serializable(value: Any) -> Any:
    """Convert a value to a JSON-serializable type."""
    from datetime import date, datetime

    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
