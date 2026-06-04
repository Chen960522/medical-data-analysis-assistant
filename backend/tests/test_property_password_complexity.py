"""Property-based tests for password complexity validation.

Validates: Requirements 8.4
Property 14: 密码复杂度验证正确性 (Password complexity validation correctness)

    For any string, the password validator SHALL accept it if and only if the
    string simultaneously satisfies ALL of the following conditions: length
    >= 8, contains at least one uppercase letter, one lowercase letter, one
    digit, and one special character. Missing any single condition SHALL cause
    the string to be rejected.

``app.core.security.validate_password_complexity`` is the source of truth for
the exact accepted shape. In particular the *special character* set is the
explicit list encoded by ``PASSWORD_SPECIAL`` in that module, so the generators
below draw special characters only from that set. These tests verify BOTH
directions of the "if and only if" property:

  * Acceptance: passwords that satisfy all five conditions are always accepted
    and return an empty error message.
  * Rejection: passwords that violate exactly one condition (too short, or
    missing uppercase / lowercase / digit / special) are always rejected and
    return a non-empty error message.
"""

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.security import PASSWORD_MIN_LENGTH, validate_password_complexity

# ---------------------------------------------------------------------------
# Character pools (mirror the implementation in app/core/security.py)
# ---------------------------------------------------------------------------

UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase
DIGITS = string.digits

# The exact set of characters accepted by PASSWORD_SPECIAL:
#   [!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]
# Decoded to the literal characters below (note the literal backslash and the
# backtick). This MUST stay in sync with security.py, which is the source of
# truth for the property.
SPECIAL = "!@#$%^&*()_+-=[]{};':\"\\|,.<>/?~`"

# Full alphabet for padding acceptance passwords: any character that belongs to
# one of the four recognised classes.
ALL_ALLOWED = UPPER + LOWER + DIGITS + SPECIAL


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def _shuffle_to_str(draw: st.DrawFn, chars: list[str]) -> str:
    """Permute ``chars`` randomly and join into a string."""
    return "".join(draw(st.permutations(chars)))


@st.composite
def valid_passwords(draw: st.DrawFn) -> str:
    """Generate a password guaranteed to satisfy ALL five conditions.

    One mandatory character from each class plus >= 4 padding characters drawn
    from the union of all allowed characters, then shuffled so the required
    characters are not always in a fixed position. Total length is always >= 8.
    """
    mandatory = [
        draw(st.sampled_from(UPPER)),
        draw(st.sampled_from(LOWER)),
        draw(st.sampled_from(DIGITS)),
        draw(st.sampled_from(SPECIAL)),
    ]
    padding = list(draw(st.text(alphabet=ALL_ALLOWED, min_size=4, max_size=24)))
    return _shuffle_to_str(draw, mandatory + padding)


@st.composite
def too_short_passwords(draw: st.DrawFn) -> str:
    """Violate ONLY the length condition.

    Contains one character from every class (so uppercase/lowercase/digit/
    special are all present) but the total length is strictly less than
    ``PASSWORD_MIN_LENGTH``.
    """
    mandatory = [
        draw(st.sampled_from(UPPER)),
        draw(st.sampled_from(LOWER)),
        draw(st.sampled_from(DIGITS)),
        draw(st.sampled_from(SPECIAL)),
    ]
    # 4 mandatory chars + 0..(MIN-5) padding => total in [4, MIN-1] < MIN.
    padding = list(
        draw(st.text(alphabet=ALL_ALLOWED, min_size=0, max_size=PASSWORD_MIN_LENGTH - 5))
    )
    return _shuffle_to_str(draw, mandatory + padding)


def _missing_class_password(draw: st.DrawFn, present: list[str], alphabet: str) -> str:
    """Build a length>=8 password that satisfies every class in ``present``.

    ``alphabet`` excludes the omitted class, guaranteeing that exactly one
    condition is violated while length is comfortably above the minimum.
    """
    mandatory = [draw(st.sampled_from(pool)) for pool in present]
    pad_min = PASSWORD_MIN_LENGTH - len(mandatory) + 1  # ensure length >= MIN
    padding = list(draw(st.text(alphabet=alphabet, min_size=pad_min, max_size=24)))
    return _shuffle_to_str(draw, mandatory + padding)


@st.composite
def missing_uppercase_passwords(draw: st.DrawFn) -> str:
    """Violate ONLY the uppercase condition."""
    return _missing_class_password(draw, [LOWER, DIGITS, SPECIAL], LOWER + DIGITS + SPECIAL)


@st.composite
def missing_lowercase_passwords(draw: st.DrawFn) -> str:
    """Violate ONLY the lowercase condition."""
    return _missing_class_password(draw, [UPPER, DIGITS, SPECIAL], UPPER + DIGITS + SPECIAL)


@st.composite
def missing_digit_passwords(draw: st.DrawFn) -> str:
    """Violate ONLY the digit condition."""
    return _missing_class_password(draw, [UPPER, LOWER, SPECIAL], UPPER + LOWER + SPECIAL)


@st.composite
def missing_special_passwords(draw: st.DrawFn) -> str:
    """Violate ONLY the special-character condition."""
    return _missing_class_password(draw, [UPPER, LOWER, DIGITS], UPPER + LOWER + DIGITS)


invalid_passwords = st.one_of(
    too_short_passwords(),
    missing_uppercase_passwords(),
    missing_lowercase_passwords(),
    missing_digit_passwords(),
    missing_special_passwords(),
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestPasswordComplexityProperties:
    """Property 14 — password complexity validation correctness (Req 8.4)."""

    @given(password=valid_passwords())
    @settings(deadline=None)
    def test_accepts_passwords_meeting_all_conditions(self, password: str) -> None:
        """Property 14 (acceptance): a password satisfying all five conditions
        is accepted and yields an empty error message.

        Validates: Requirements 8.4
        """
        is_valid, message = validate_password_complexity(password)
        assert is_valid is True, f"expected valid: {password!r} (message={message!r})"
        assert message == "", f"valid password must have empty message, got {message!r}"

    @given(password=too_short_passwords())
    @settings(deadline=None)
    def test_rejects_too_short(self, password: str) -> None:
        """Property 14 (rejection): a password shorter than the minimum length
        is rejected even when it contains every character class.

        Validates: Requirements 8.4
        """
        self._assert_rejected(password)

    @given(password=missing_uppercase_passwords())
    @settings(deadline=None)
    def test_rejects_missing_uppercase(self, password: str) -> None:
        """Property 14 (rejection): a password without an uppercase letter is
        rejected.

        Validates: Requirements 8.4
        """
        self._assert_rejected(password)

    @given(password=missing_lowercase_passwords())
    @settings(deadline=None)
    def test_rejects_missing_lowercase(self, password: str) -> None:
        """Property 14 (rejection): a password without a lowercase letter is
        rejected.

        Validates: Requirements 8.4
        """
        self._assert_rejected(password)

    @given(password=missing_digit_passwords())
    @settings(deadline=None)
    def test_rejects_missing_digit(self, password: str) -> None:
        """Property 14 (rejection): a password without a digit is rejected.

        Validates: Requirements 8.4
        """
        self._assert_rejected(password)

    @given(password=missing_special_passwords())
    @settings(deadline=None)
    def test_rejects_missing_special(self, password: str) -> None:
        """Property 14 (rejection): a password without a special character is
        rejected.

        Validates: Requirements 8.4
        """
        self._assert_rejected(password)

    @staticmethod
    def _assert_rejected(password: str) -> None:
        is_valid, message = validate_password_complexity(password)
        assert is_valid is False, f"expected invalid: {password!r}"
        assert isinstance(message, str) and message, (
            f"invalid password must have a non-empty error message, got {message!r}"
        )


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestPasswordComplexityExamples:
    """Representative example-based regressions for Property 14 (Req 8.4)."""

    VALID_EXAMPLES = [
        "StrongPass1!",
        "NewStrong1!",
    ]

    # (password, reason) pairs — each violates exactly one condition.
    INVALID_EXAMPLES = [
        ("weakpass1!", "no uppercase"),
        ("WeakPass!!", "no digit"),
        ("WeakPass11", "no special character"),
        ("Sh1!", "too short"),
    ]

    def test_valid_examples_are_accepted(self) -> None:
        """Req 8.4: representative valid passwords are accepted with no error."""
        for password in self.VALID_EXAMPLES:
            is_valid, message = validate_password_complexity(password)
            assert is_valid is True, f"expected valid: {password!r}"
            assert message == "", f"valid password must have empty message, got {message!r}"

    def test_invalid_examples_are_rejected(self) -> None:
        """Req 8.4: representative invalid passwords are rejected with a message."""
        for password, reason in self.INVALID_EXAMPLES:
            is_valid, message = validate_password_complexity(password)
            assert is_valid is False, f"expected invalid ({reason}): {password!r}"
            assert isinstance(message, str) and message, (
                f"invalid password ({reason}) must have a non-empty message"
            )
