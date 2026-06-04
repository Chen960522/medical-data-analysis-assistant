/**
 * Data-file TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/data.py`.
 */

export interface DataFile {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  file_format: string;
  s3_key: string;
  row_count: number | null;
  column_count: number | null;
  status: string;
  created_at: string;
}

export interface DataFileListResponse {
  files: DataFile[];
  total: number;
}

export interface UploadResponse {
  message: string;
  file: DataFile;
}

/**
 * Data preview (first 10 rows) — mirrors `DataPreviewResponse`.
 *
 * Backs the data preview table on the analysis page (Req 2.2).
 */
export interface DataPreviewResponse {
  file_id: string;
  filename: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
  total_columns: number;
}

/** Quality info for a single column — mirrors `ColumnQuality`. */
export interface ColumnQuality {
  name: string;
  dtype: string;
  missing_count: number;
  missing_percentage: number;
}

/**
 * Data quality report — mirrors `DataQualityResponse`.
 *
 * Backs the data quality summary display (Req 2.6).
 */
export interface DataQualityResponse {
  file_id: string;
  filename: string;
  total_rows: number;
  total_columns: number;
  missing_value_percentage: number;
  columns: ColumnQuality[];
}
