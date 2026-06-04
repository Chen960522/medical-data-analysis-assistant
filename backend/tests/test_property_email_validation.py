"""Property-based tests for email format validation.

Validates: Requirements 8.2
Property 13: 邮箱格式验证正确性 (Email format validation correctness)

    For any string, the email validator SHALL accept it if and only if the
    string conforms to standard email format (contains an @ symbol and a valid
    domain part), and SHALL reject all strings that do not conform.

The implementation under test is the source of truth for the exact accepted
shape (RFC 5322 simplified). These tests verify BOTH directions of the
"if and only if" property:

  * Acceptance: well-formed emails (valid local part + ``@`` + dotted domain)
    are always accepted.
  * Rejection: malformed strings (no ``@``, empty local/domain, invalid domain
    label, embedded whitespace, empty string, over-length) are always rejected.
"""

import string

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.security import validate_email_format

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Characters allowed in the local part by EMAIL_REGEX in app/core/security.py.
ALNUM = string.ascii_letters + string.digits
LOCAL_CHARS = ALNUM + "!#$%&'*+/=?^_`{|}~.-"

# Printable ASCII that excludes the ``@`` sign, used to build strings that can
# never match (a literal ``@`` is required by the regex).
PRINTABLE_NO_AT = "".join(c for c in string.printable if c not in "@\r\n\x0b\x0c\t ")

# A non-empty local part: one or more allowed characters, bounded for length.
local_part = st.text(alphabet=LOCAL_CHARS, min_size=1, max_size=20)


@st.composite
def domain_label(draw: st.DrawFn) -> str:
    """Generate a single valid domain label.

    Mirrors the regex label shape: an alnum char optionally followed by a run
    of ``[a-zA-Z0-9-]`` and a trailing alnum char (so a label never starts or
    ends with a hyphen).
    """
    first = draw(st.sampled_from(ALNUM))
    if draw(st.booleans()):
        middle = draw(st.text(alphabet=ALNUM + "-", min_size=0, max_size=10))
        last = draw(st.sampled_from(ALNUM))
        return first + middle + last
    return first


# A domain with at least one dot (>= 2 dot-separated labels).
dotted_domain = st.lists(domain_label(), min_size=2, max_size=4).map(".".join)


@st.composite
def valid_emails(draw: st.DrawFn) -> str:
    """Generate a string that conforms to the standard email format."""
    email = f"{draw(local_part)}@{draw(dotted_domain)}"
    assume(len(email) <= 255)
    return email


# --- Generators for strings that must be rejected ------------------------- #


@st.composite
def no_at_strings(draw: st.DrawFn) -> str:
    """Non-empty strings that contain no ``@`` and therefore cannot match."""
    return draw(st.text(alphabet=PRINTABLE_NO_AT, min_size=1, max_size=40))


@st.composite
def empty_local(draw: st.DrawFn) -> str:
    """``@domain`` with a missing local part."""
    return f"@{draw(dotted_domain)}"


@st.composite
def empty_domain(draw: st.DrawFn) -> str:
    """``local@`` with a missing domain part."""
    return f"{draw(local_part)}@"


@st.composite
def leading_dot_domain(draw: st.DrawFn) -> str:
    """Domain begins with a dot, so its first label is invalid."""
    return f"{draw(local_part)}@.{draw(domain_label())}"


@st.composite
def whitespace_emails(draw: st.DrawFn) -> str:
    """A valid email with a single whitespace char inserted somewhere."""
    email = draw(valid_emails())
    ws = draw(st.sampled_from([" ", "\t", "\n"]))
    # Keep the insertion position strictly before the final character so the
    # whitespace is never trailing. Python's ``$`` anchor matches just before a
    # trailing newline, which would otherwise let ``"...com\n"`` slip through.
    pos = draw(st.integers(min_value=0, max_value=len(email) - 1))
    return email[:pos] + ws + email[pos:]


@st.composite
def over_length_emails(draw: st.DrawFn) -> str:
    """A structurally fine email whose total length exceeds 255 chars."""
    local_len = draw(st.integers(min_value=250, max_value=300))
    return ("a" * local_len) + "@example.com"


invalid_emails = st.one_of(
    no_at_strings(),
    empty_local(),
    empty_domain(),
    leading_dot_domain(),
    whitespace_emails(),
    over_length_emails(),
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestEmailValidationProperties:
    """Property 13 — email validation correctness (Req 8.2)."""

    @given(email=valid_emails())
    @settings(deadline=None)
    def test_accepts_well_formed_emails(self, email: str) -> None:
        """Property 13 (acceptance): any well-formed email is accepted.

        Validates: Requirements 8.2
        """
        assert validate_email_format(email) is True, f"expected valid: {email!r}"

    @given(email=invalid_emails)
    @settings(deadline=None)
    def test_rejects_malformed_strings(self, email: str) -> None:
        """Property 13 (rejection): any malformed string is rejected.

        Validates: Requirements 8.2
        """
        assert validate_email_format(email) is False, f"expected invalid: {email!r}"


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestEmailValidationExamples:
    """Representative example-based regressions for Property 13 (Req 8.2)."""

    VALID_EXAMPLES = [
        "user@example.com",
        "a.b+c@sub.domain.co",
        "first.last@example.org",
        "x@a.io",
        "weird!#$%&'*+/=?^_`{|}~-@example.com",
    ]

    INVALID_EXAMPLES = [
        "not-an-email",          # no @
        "@nodomain.com",         # empty local part
        "nolocal@",              # empty domain
        "spaces in@email.com",   # embedded whitespace
        "user@.com",             # domain starts with a dot
        "user@-bad.com",         # domain label starts with a hyphen
        "",                      # empty string
        "a" * 256 + "@example.com",  # exceeds 255 chars
    ]

    def test_valid_examples_are_accepted(self) -> None:
        """Req 8.2: representative valid emails are accepted."""
        for email in self.VALID_EXAMPLES:
            assert validate_email_format(email) is True, f"expected valid: {email!r}"

    def test_invalid_examples_are_rejected(self) -> None:
        """Req 8.2: representative invalid emails are rejected."""
        for email in self.INVALID_EXAMPLES:
            assert validate_email_format(email) is False, f"expected invalid: {email!r}"
