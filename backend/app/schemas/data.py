"""Data file request/response schemas."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DataFileResponse(BaseModel):
    """Response schema for a data file record."""

    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    file_format: str
    s3_key: str
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DataFileListResponse(BaseModel):
    """Response schema for listing data files."""

    files: list[DataFileResponse]
    total: int


class DataPreviewResponse(BaseModel):
    """Response schema for data preview (first 10 rows)."""

    file_id: uuid.UUID
    filename: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    total_columns: int


class ColumnQuality(BaseModel):
    """Quality info for a single column."""

    name: str
    dtype: str
    missing_count: int
    missing_percentage: float


class DataQualityResponse(BaseModel):
    """Response schema for data quality report."""

    file_id: uuid.UUID
    filename: str
    total_rows: int
    total_columns: int
    missing_value_percentage: float
    columns: list[ColumnQuality]


class UploadResponse(BaseModel):
    """Response schema for file upload."""

    message: str
    file: DataFileResponse


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
