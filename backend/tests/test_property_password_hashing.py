"""Property-based tests for password hashing security.

Validates: Requirements 8.6
Property 15: 密码哈希安全性 (Password hashing security)

    For any password string, after bcrypt hashing:
      (1) the hash value does NOT equal the original password,
      (2) verifying the hash with the correct password returns ``True``,
      (3) verifying the same hash with any DIFFERENT password returns ``False``.

Requirement 8.6 further requires that passwords are stored using bcrypt with a
cost factor of at least 12. The cost factor is embedded in the produced hash
(the number between the 2nd and 3rd ``$`` of a ``$2b$<cost>$...`` modular-crypt
string), so these tests assert against the *actual* produced hash rather than
trusting the configured value alone.

``app.core.security.hash_password`` / ``verify_password`` are the source of
truth and are NOT modified by these tests.

bcrypt 72-byte constraint
-------------------------
The bcrypt algorithm only consumes the first 72 bytes of a password, and
passlib 1.7.4 raises a ``ValueError`` when handed a password longer than 72
bytes. Generated passwords are therefore bounded so their UTF-8 *encoded* byte
length never exceeds 72 (a single character can encode to up to 4 bytes, so a
char-count limit alone is insufficient). This keeps the tests robust against
passlib's length guard while still exercising a wide input space.

bcrypt hashing is deliberately slow (cost factor >= 12 ⇒ 2**12 key-expansion
rounds), so the Hypothesis example counts below are kept modest to keep the
suite fast and non-flaky; ``deadline=None`` disables per-example time limits.
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.config import settings as app_settings
from app.core.security import hash_password, verify_password

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Maximum number of bytes bcrypt / passlib will accept for a password.
BCRYPT_MAX_BYTES = 72


def _within_bcrypt_limit(password: str) -> bool:
    """True iff ``password`` fits within bcrypt's 72-byte input window.

    Uses the UTF-8 encoded byte length (not the character count) because a
    single Unicode character can encode to as many as 4 bytes; a char-count
    bound alone would still let passlib's 72-byte guard fire.
    """
    return 1 <= len(password.encode("utf-8")) <= BCRYPT_MAX_BYTES


# Draw arbitrary (incl. multi-byte) text, cap the char count for efficiency,
# then filter to guarantee the encoded byte length stays within bcrypt's limit.
#
# NULL bytes ("\x00") are excluded from the alphabet (via ``min_codepoint=1``)
# because passlib's bcrypt backend rejects them outright (``PasswordValueError:
# bcrypt does not allow NULL bytes in password``). This matches real password
# input, which never contains NULL bytes: ``validate_password_complexity`` only
# accepts printable characters, so NULL-byte input would be rejected before ever
# reaching ``hash_password`` in the registration flow.
#
# Surrogate codepoints (Unicode category "Cs", U+D800–U+DFFF) are also excluded
# (via ``exclude_categories=("Cs",)``) because they are lone UTF-16 surrogates
# that Python cannot encode to UTF-8 (``UnicodeEncodeError: surrogates not
# allowed``). They are not valid UTF-8-encodable password input and would crash
# ``_within_bcrypt_limit``'s ``password.encode("utf-8")`` call.
passwords = st.text(
    alphabet=st.characters(min_codepoint=1, exclude_categories=("Cs",)),
    min_size=1,
    max_size=BCRYPT_MAX_BYTES,
).filter(_within_bcrypt_limit)


def _parse_bcrypt_cost(hashed: str) -> int:
    """Extract the embedded cost factor from a ``$2b$<cost>$...`` bcrypt hash.

    The modular-crypt format splits on ``$`` into
    ``['', ident, cost, salt+digest]`` so the cost is the third field.
    """
    parts = hashed.split("$")
    assert len(parts) >= 4, f"unexpected bcrypt hash format: {hashed!r}"
    return int(parts[2])


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestPasswordHashingProperties:
    """Property 15 — password hashing security (Req 8.6)."""

    # bcrypt is intentionally slow; keep example counts modest and disable the
    # per-example deadline so a single slow hash cannot mark the test flaky.
    @given(password=passwords)
    @settings(max_examples=20, deadline=None)
    def test_hash_differs_from_original(self, password: str) -> None:
        """Property 15 (1): the bcrypt hash never equals the plaintext password.

        Validates: Requirements 8.6
        """
        hashed = hash_password(password)
        assert hashed != password, "hash must not equal the original password"

    @given(password=passwords)
    @settings(max_examples=20, deadline=None)
    def test_correct_password_verifies_true(self, password: str) -> None:
        """Property 15 (2): verifying a hash with the correct password is True.

        Validates: Requirements 8.6
        """
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    @given(password=passwords, other=passwords)
    @settings(max_examples=20, deadline=None)
    def test_different_password_verifies_false(self, password: str, other: str) -> None:
        """Property 15 (3): verifying a hash with a DIFFERENT password is False.

        Validates: Requirements 8.6
        """
        assume(password != other)
        hashed = hash_password(password)
        assert verify_password(other, hashed) is False

    @given(password=passwords)
    @settings(max_examples=20, deadline=None)
    def test_hash_uses_bcrypt_cost_factor_at_least_12(self, password: str) -> None:
        """Property 15 / Req 8.6: produced hash is bcrypt ``$2b$`` with cost >= 12.

        Asserts against the cost embedded in the actual hash, not just the
        configured value.

        Validates: Requirements 8.6
        """
        hashed = hash_password(password)
        assert hashed.startswith("$2b$"), f"expected bcrypt 2b hash, got {hashed!r}"
        cost = _parse_bcrypt_cost(hashed)
        assert cost >= 12, f"bcrypt cost factor must be >= 12, got {cost}"


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestPasswordHashingExamples:
    """Representative example-based regressions for Property 15 (Req 8.6)."""

    EXAMPLE_PASSWORDS = [
        "StrongPass1!",
        "NewStrong1!",
        "p",  # minimal single-character password
        "münchën-Pä55!",  # multi-byte UTF-8 characters
    ]

    def test_hash_differs_from_original(self) -> None:
        """Property 15 (1): hash never equals the plaintext for representatives."""
        for password in self.EXAMPLE_PASSWORDS:
            assert hash_password(password) != password

    def test_correct_password_verifies_true(self) -> None:
        """Property 15 (2): correct password verifies True for representatives."""
        for password in self.EXAMPLE_PASSWORDS:
            assert verify_password(password, hash_password(password)) is True

    def test_different_password_verifies_false(self) -> None:
        """Property 15 (3): a different password verifies False for representatives."""
        hashed = hash_password("StrongPass1!")
        for wrong in ["StrongPass1?", "strongpass1!", "wrong", "StrongPass1! "]:
            assert verify_password(wrong, hashed) is False

    def test_hash_uses_bcrypt_cost_factor_at_least_12(self) -> None:
        """Req 8.6: produced hash is bcrypt ``$2b$`` with embedded cost >= 12."""
        for password in self.EXAMPLE_PASSWORDS:
            hashed = hash_password(password)
            assert hashed.startswith("$2b$"), f"expected bcrypt 2b hash, got {hashed!r}"
            assert _parse_bcrypt_cost(hashed) >= 12

    def test_configured_cost_factor_matches_requirement(self) -> None:
        """Req 8.6: the configured bcrypt cost factor is at least 12."""
        assert app_settings.bcrypt_cost_factor >= 12

    def test_same_password_yields_distinct_hashes(self) -> None:
        """bcrypt salts each hash, so two hashes of one password differ yet both verify."""
        password = "StrongPass1!"
        first = hash_password(password)
        second = hash_password(password)
        assert first != second, "bcrypt must use a random salt per hash"
        assert verify_password(password, first) is True
        assert verify_password(password, second) is True
