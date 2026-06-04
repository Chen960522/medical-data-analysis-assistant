"""Property-based tests for data-upload file format validation.

Validates: Requirements 1.1, 1.5
Property 1: 文件格式验证正确性 (File format validation correctness)

    For any filename string, the data-upload format validator SHALL accept the
    file if and only if the file extension is ``.csv``, ``.xlsx``, ``.xls`` or
    ``.json`` (case-insensitive), and SHALL reject all other extensions.

The production implementation in ``app/api/v1/data.py`` is the source of truth
for the exact accepted shape:

  * ``_get_file_extension(filename)`` returns the lowercased extension including
    the leading dot (or ``""`` when there is no dot).
  * ``_validate_file(upload)`` raises ``HTTPException`` (422) when the filename
    is empty or its extension is not in ``ALLOWED_EXTENSIONS``; otherwise it
    returns the extension.

These tests verify BOTH directions of the "if and only if" property:

  * Acceptance: filenames whose final extension is one of the allowed set (in
    any letter case) are always accepted and return the lowercased extension.
  * Rejection: filenames with any other extension, and filenames with no
    extension, are always rejected with a 422 error that lists the supported
    formats (satisfying Req 1.5).
"""

import io
import string

import pytest
from fastapi import HTTPException, UploadFile
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.api.v1.data import ALLOWED_EXTENSIONS, _get_file_extension, _validate_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Allowed extensions without the leading dot, as the validator stores them.
ALLOWED_EXTS_NO_DOT = ["csv", "xlsx", "xls", "json"]

# Characters that are safe to use inside a base name. Dots are allowed because
# the extension is always taken from the LAST dot, and an explicit ``.ext`` is
# appended after the base in the acceptance/rejection strategies.
BASE_CHARS = string.ascii_letters + string.digits + "_-. "

# A base name alphabet that contains no dot, used to build filenames that have
# no extension at all.
NO_DOT_CHARS = "".join(c for c in (string.ascii_letters + string.digits + "_- ") if c != ".")


def make_upload(filename: str) -> UploadFile:
    """Build a FastAPI ``UploadFile`` with an empty body and the given name."""
    return UploadFile(filename=filename, file=io.BytesIO(b""))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

base_names = st.text(alphabet=BASE_CHARS, min_size=0, max_size=30)
no_ext_filenames = st.text(alphabet=NO_DOT_CHARS, min_size=1, max_size=30)


@st.composite
def cased_ext(draw: st.DrawFn) -> str:
    """Pick an allowed extension and randomize the letter case of each char."""
    ext = draw(st.sampled_from(ALLOWED_EXTS_NO_DOT))
    return "".join(draw(st.sampled_from([c.lower(), c.upper()])) for c in ext)


@st.composite
def accepted_filenames(draw: st.DrawFn) -> str:
    """A filename whose final extension is one of the allowed set (any case)."""
    base = draw(base_names)
    ext = draw(cased_ext())
    return f"{base}.{ext}"


@st.composite
def bad_ext(draw: st.DrawFn) -> str:
    """An alphabetic extension that is NOT one of the allowed set."""
    ext = draw(st.text(alphabet=string.ascii_letters, min_size=1, max_size=8))
    assume(("." + ext.lower()) not in ALLOWED_EXTENSIONS)
    return ext


@st.composite
def rejected_bad_ext_filenames(draw: st.DrawFn) -> str:
    """A filename whose final extension is not in the allowed set."""
    base = draw(base_names)
    ext = draw(bad_ext())
    return f"{base}.{ext}"


# Strings the validator must reject: wrong extension, or no extension at all.
rejected_filenames = st.one_of(rejected_bad_ext_filenames(), no_ext_filenames)


# ---------------------------------------------------------------------------
# Property tests — Property 1 (Req 1.1, 1.5)
# ---------------------------------------------------------------------------


class TestFileFormatValidationProperties:
    """Property 1 — file format validation correctness (Req 1.1, 1.5)."""

    @given(filename=accepted_filenames())
    @settings(deadline=None)
    def test_accepts_allowed_extensions(self, filename: str) -> None:
        """Property 1 (acceptance): allowed extensions are accepted.

        Validates: Requirements 1.1
        """
        ext = _validate_file(make_upload(filename))
        assert ext in ALLOWED_EXTENSIONS, f"expected accepted: {filename!r}"
        # The returned extension is the lowercased dotted extension.
        assert ext == _get_file_extension(filename)

    @given(filename=rejected_filenames)
    @settings(deadline=None)
    def test_rejects_disallowed_extensions(self, filename: str) -> None:
        """Property 1 (rejection): any other extension is rejected with 422.

        Req 1.5: the error message lists the supported formats.

        Validates: Requirements 1.1, 1.5
        """
        with pytest.raises(HTTPException) as exc_info:
            _validate_file(make_upload(filename))
        assert exc_info.value.status_code == 422, f"expected rejected: {filename!r}"
        # Req 1.5: the error must enumerate every supported format.
        detail = str(exc_info.value.detail)
        for allowed in ALLOWED_EXTENSIONS:
            assert allowed in detail, f"supported format {allowed} missing from: {detail!r}"

    def test_rejects_empty_filename(self) -> None:
        """An empty filename is rejected with a 422 'Filename is required'.

        Validates: Requirements 1.5
        """
        with pytest.raises(HTTPException) as exc_info:
            _validate_file(make_upload(""))
        assert exc_info.value.status_code == 422
        assert "Filename is required" in str(exc_info.value.detail)


class TestGetFileExtensionProperties:
    """Property 1 helper — extension parsing in ``_get_file_extension``."""

    @given(base=base_names, ext=cased_ext())
    @settings(deadline=None)
    def test_allowed_ext_parsed_lowercased(self, base: str, ext: str) -> None:
        """For any base + allowed ext, the parsed extension is the lowercased dotted ext.

        Validates: Requirements 1.1
        """
        filename = f"{base}.{ext}"
        assert _get_file_extension(filename) == "." + ext.lower()

    @given(name=no_ext_filenames)
    @settings(deadline=None)
    def test_no_dot_returns_empty(self, name: str) -> None:
        """A filename with no dot has no extension.

        Validates: Requirements 1.1
        """
        assume("." not in name)
        assert _get_file_extension(name) == ""


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestFileFormatValidationExamples:
    """Representative example-based regressions for Property 1 (Req 1.1, 1.5)."""

    # (filename, expected lowercased dotted extension)
    ACCEPTED_EXAMPLES = [
        ("data.csv", ".csv"),
        ("report.XLSX", ".xlsx"),
        ("legacy.xls", ".xls"),
        ("payload.json", ".json"),
        ("archive.tar.csv", ".csv"),  # accepted: last extension is .csv
        ("UPPER.CSV", ".csv"),
        ("file.Json", ".json"),
    ]

    REJECTED_EXAMPLES = [
        "data.txt",
        "image.png",
        "script.py",
        "noextension",       # no dot at all
        "wrong.csvx",        # near-miss extension
        ".csvx",             # leading dot, wrong extension
        "data.csv.bak",      # last extension is .bak
        "report.",           # trailing dot -> extension is "."
    ]

    def test_accepted_examples(self) -> None:
        """Req 1.1: representative supported filenames are accepted."""
        for filename, expected in self.ACCEPTED_EXAMPLES:
            ext = _validate_file(make_upload(filename))
            assert ext == expected, f"expected {expected} for {filename!r}, got {ext!r}"
            assert ext in ALLOWED_EXTENSIONS

    def test_rejected_examples(self) -> None:
        """Req 1.5: representative unsupported filenames are rejected with 422."""
        for filename in self.REJECTED_EXAMPLES:
            with pytest.raises(HTTPException) as exc_info:
                _validate_file(make_upload(filename))
            assert exc_info.value.status_code == 422, f"expected rejected: {filename!r}"
