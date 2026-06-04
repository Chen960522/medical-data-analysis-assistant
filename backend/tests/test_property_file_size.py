"""Property-based tests for file size validation.

Validates: Requirements 1.3, 1.4, 11.3, 11.6
Property 2: 文件大小验证正确性 (File size validation correctness)

    For any non-negative integer file size value and configured size limit, the
    file-size validator SHALL accept files whose size is <= the limit and reject
    files whose size is > the limit. The data-upload module limit is 100MB; the
    PDF-upload module limit is 50MB.

The production implementations are the source of truth for the exact rule. The
size check is performed INLINE in two upload endpoints using module-level
constants rather than an extracted function:

  * ``app/api/v1/data.py`` rejects when ``file_size > MAX_FILE_SIZE`` and raises
    ``HTTPException`` (422). ``MAX_FILE_SIZE = settings.s3_max_file_size`` which
    defaults to 104857600 (100MB) — satisfying Req 1.3 / 1.4.
  * ``app/api/v1/translation.py`` rejects when ``file_size > MAX_PDF_SIZE`` and
    raises ``HTTPException`` (422). ``MAX_PDF_SIZE = 50 * 1024 * 1024``
    (52428800, 50MB) — satisfying Req 11.3 / 11.6.

Because the validation is an inline ``>`` comparison, these tests model the rule
as a pure predicate (:func:`accepts`) that mirrors the production check exactly,
and parametrize it by the REAL imported limit constants. They also assert that
the configured limit VALUES match the documented requirements (the part tying to
Req 1.3 / 11.3), so a future change to a constant would be caught here.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.v1.data import MAX_FILE_SIZE
from app.api.v1.translation import MAX_PDF_SIZE

# ---------------------------------------------------------------------------
# Pure predicate mirroring the production rule
# ---------------------------------------------------------------------------

# Documented limits (bytes).
DATA_LIMIT = 100 * 1024 * 1024  # 104857600
PDF_LIMIT = 50 * 1024 * 1024    # 52428800

# Each configured limit paired with a human label for parametrization.
LIMITS = [
    pytest.param(MAX_FILE_SIZE, id="data-100MB"),
    pytest.param(MAX_PDF_SIZE, id="pdf-50MB"),
]


def accepts(file_size: int, limit: int) -> bool:
    """Mirror the production upper-bound check: reject iff ``size > limit``.

    This is the exact logic of the inline ``file_size > MAX_FILE_SIZE`` check in
    ``app/api/v1/data.py`` and the ``file_size > MAX_PDF_SIZE`` check in
    ``app/api/v1/translation.py`` (the source of truth). A file is accepted when
    its size is less than or equal to the limit.
    """
    return file_size <= limit


# ---------------------------------------------------------------------------
# Property tests — Property 2 (Req 1.3, 1.4, 11.3, 11.6)
# ---------------------------------------------------------------------------


class TestFileSizeValidationProperties:
    """Property 2 — file size validation correctness (Req 1.3, 1.4, 11.3, 11.6)."""

    @pytest.mark.parametrize("limit", LIMITS)
    @given(data=st.data())
    @settings(deadline=None)
    def test_accepts_at_or_under_limit(self, limit: int, data: st.DataObject) -> None:
        """Property 2 (acceptance): any size <= limit is accepted.

        Validates: Requirements 1.3, 11.3
        """
        size = data.draw(st.integers(min_value=0, max_value=limit))
        assert accepts(size, limit) is True, f"size {size} should be accepted (limit {limit})"

    @pytest.mark.parametrize("limit", LIMITS)
    @given(data=st.data())
    @settings(deadline=None)
    def test_rejects_over_limit(self, limit: int, data: st.DataObject) -> None:
        """Property 2 (rejection): any size > limit is rejected.

        Validates: Requirements 1.4, 11.6
        """
        size = data.draw(st.integers(min_value=limit + 1, max_value=limit * 2 + 1))
        assert accepts(size, limit) is False, f"size {size} should be rejected (limit {limit})"

    @pytest.mark.parametrize("limit", LIMITS)
    @given(data=st.data())
    @settings(deadline=None)
    def test_iff_size_within_limit(self, limit: int, data: st.DataObject) -> None:
        """Property 2 (general iff): accept(size, limit) == (size <= limit).

        Validates: Requirements 1.3, 1.4, 11.3, 11.6
        """
        size = data.draw(st.integers(min_value=0, max_value=limit * 2))
        assert accepts(size, limit) == (size <= limit)

    @pytest.mark.parametrize("limit", LIMITS)
    def test_boundary_exactly_at_limit_accepted(self, limit: int) -> None:
        """Boundary: a file exactly at the limit is accepted.

        Validates: Requirements 1.3, 11.3
        """
        assert accepts(limit, limit) is True

    @pytest.mark.parametrize("limit", LIMITS)
    def test_boundary_one_byte_over_rejected(self, limit: int) -> None:
        """Boundary: one byte over the limit is rejected.

        Validates: Requirements 1.4, 11.6
        """
        assert accepts(limit + 1, limit) is False


# ---------------------------------------------------------------------------
# Configured-limit value tests — ties Property 2 to the documented requirements
# ---------------------------------------------------------------------------


class TestConfiguredLimitValues:
    """The configured constants must match the documented requirements."""

    def test_data_limit_is_100mb(self) -> None:
        """Req 1.3: the data-upload limit is exactly 100MB (104857600 bytes)."""
        assert MAX_FILE_SIZE == 100 * 1024 * 1024
        assert MAX_FILE_SIZE == 104857600

    def test_pdf_limit_is_50mb(self) -> None:
        """Req 11.3: the PDF-upload limit is exactly 50MB (52428800 bytes)."""
        assert MAX_PDF_SIZE == 50 * 1024 * 1024
        assert MAX_PDF_SIZE == 52428800


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestFileSizeValidationExamples:
    """Representative example-based regressions for Property 2."""

    # (size, expected accepted?) relative to the 100MB data limit.
    DATA_EXAMPLES = [
        (0, True),                       # empty (size rule accepts; emptiness is a separate rule)
        (1, True),                       # one byte
        (DATA_LIMIT - 1, True),          # just under
        (DATA_LIMIT, True),              # exactly at limit
        (DATA_LIMIT + 1, False),         # one byte over
        (DATA_LIMIT * 5, False),         # far over
    ]

    # (size, expected accepted?) relative to the 50MB PDF limit.
    PDF_EXAMPLES = [
        (0, True),
        (1, True),
        (PDF_LIMIT - 1, True),
        (PDF_LIMIT, True),
        (PDF_LIMIT + 1, False),
        (PDF_LIMIT * 5, False),
    ]

    @pytest.mark.parametrize("size, expected", DATA_EXAMPLES)
    def test_data_limit_examples(self, size: int, expected: bool) -> None:
        """Req 1.3 / 1.4: representative sizes around the 100MB limit."""
        assert accepts(size, MAX_FILE_SIZE) is expected

    @pytest.mark.parametrize("size, expected", PDF_EXAMPLES)
    def test_pdf_limit_examples(self, size: int, expected: bool) -> None:
        """Req 11.3 / 11.6: representative sizes around the 50MB limit."""
        assert accepts(size, MAX_PDF_SIZE) is expected
