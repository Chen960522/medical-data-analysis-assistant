"""Property-based tests for user data isolation.

Validates: Requirements 8.17, 8.18, 8.19, 8.21, 8.22
Property 16: 用户数据隔离正确性 (User data isolation correctness)

    For any two distinct users A and B, with an arbitrary number of records
    owned by each, user A's scoped data query SHALL return only records
    belonging to user A and SHALL NEVER include records belonging to user B,
    and vice versa. Cross-user access to a specific resource SHALL be denied
    with 403 Forbidden.

The access-control helpers under ``app.middleware.access_control`` are the
source of truth and are NOT modified by these tests:

    * ``get_user_scoped_query``   — appends ``WHERE model.user_id == user_id``
      to a SQLAlchemy ``Select`` (Req 8.18, 8.22).
    * ``verify_resource_ownership`` — raises 403 if the resource's ``user_id``
      does not match, 404 if the resource is ``None`` (Req 8.21).
    * ``get_resource_or_deny``    — loads a resource by id then enforces
      ownership: 404 if missing, 403 if owned by another user (Req 8.21).

Performance notes
-----------------
Each Hypothesis example builds and tears down a FRESH in-memory SQLite
database inside the test body (rather than via a function-scoped fixture) so
that examples never leak state into one another and so the
``function_scoped_fixture`` health check is never triggered. Generated users
are stored with a constant dummy password hash — Property 16 concerns query
isolation only, not password verification, so the (deliberately slow) bcrypt
``hash_password`` is intentionally avoided inside generated loops to keep the
suite fast. ``deadline=None`` disables per-example time limits because each
example performs schema setup.
"""

import uuid
from contextlib import contextmanager

import pytest
from fastapi import HTTPException, status
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.middleware.access_control import (
    get_resource_or_deny,
    get_user_scoped_query,
    verify_resource_ownership,
)
from app.models.base import Base
from app.models.data import DataFile
from app.models.user import User

# A constant, valid-looking bcrypt hash. Property 16 only exercises query
# isolation, so we deliberately avoid the slow bcrypt key-expansion that
# ``hash_password`` performs for every generated user.
DUMMY_PASSWORD_HASH = "$2b$12$" + "x" * 53


@contextmanager
def fresh_session():
    """Yield a session bound to a brand-new in-memory SQLite database.

    The engine, schema and session are created and torn down per call so that
    each Hypothesis example runs against fully isolated state.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_user(session, email: str) -> User:
    """Create and persist a verified user with the given email."""
    user = User(
        email=email,
        password_hash=DUMMY_PASSWORD_HASH,
        is_verified=True,
        is_locked=False,
        failed_login_count=0,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_files(session, user: User, count: int, label: str) -> None:
    """Persist ``count`` DataFile records owned by ``user``."""
    for i in range(count):
        session.add(
            DataFile(
                user_id=user.id,
                filename=f"{label}_{i}.csv",
                original_filename=f"{label}_{i}.csv",
                file_size=1024 + i,
                file_format="csv",
                s3_key=f"uploads/{label}/{i}.csv",
                status="uploaded",
            )
        )
    session.commit()


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestUserDataIsolationProperties:
    """Property 16 — user data isolation correctness (Req 8.17-8.22)."""

    @given(
        n_a=st.integers(min_value=0, max_value=8),
        n_b=st.integers(min_value=0, max_value=8),
    )
    @settings(max_examples=40, deadline=None)
    def test_scoped_query_returns_only_owner_records(self, n_a: int, n_b: int) -> None:
        """A scoped query returns exactly the owner's records and never the other's.

        For two distinct users A and B with ``n_a``/``n_b`` files respectively:
          * A's scoped query returns exactly ``n_a`` rows, all owned by A and
            none owned by B.
          * B's scoped query returns exactly ``n_b`` rows, all owned by B and
            none owned by A (the "vice versa" half of Property 16).

        Validates: Requirements 8.18, 8.19, 8.22
        """
        with fresh_session() as session:
            user_a = _make_user(session, f"a_{uuid.uuid4().hex}@example.com")
            user_b = _make_user(session, f"b_{uuid.uuid4().hex}@example.com")
            assert user_a.id != user_b.id

            _make_files(session, user_a, n_a, "a")
            _make_files(session, user_b, n_b, "b")

            a_results = session.execute(
                get_user_scoped_query(select(DataFile), DataFile, user_a.id)
            ).scalars().all()
            b_results = session.execute(
                get_user_scoped_query(select(DataFile), DataFile, user_b.id)
            ).scalars().all()

            # A sees exactly its own records, never B's.
            assert len(a_results) == n_a
            assert all(f.user_id == user_a.id for f in a_results)
            assert all(f.user_id != user_b.id for f in a_results)

            # Vice versa: B sees exactly its own records, never A's.
            assert len(b_results) == n_b
            assert all(f.user_id == user_b.id for f in b_results)
            assert all(f.user_id != user_a.id for f in b_results)

            # The two result sets are disjoint by primary key.
            a_ids = {f.id for f in a_results}
            b_ids = {f.id for f in b_results}
            assert a_ids.isdisjoint(b_ids)

    @given(owner_id=st.uuids(), other_id=st.uuids())
    @settings(max_examples=50, deadline=None)
    def test_verify_ownership_admits_owner_denies_others(
        self, owner_id: uuid.UUID, other_id: uuid.UUID
    ) -> None:
        """Ownership check passes for the owner and 403s for any distinct user.

        Uses a lightweight stand-in object exposing only the ``user_id``
        attribute that ``verify_resource_ownership`` inspects.

        Validates: Requirements 8.21
        """
        assume(owner_id != other_id)

        class _OwnedResource:
            def __init__(self, user_id: uuid.UUID) -> None:
                self.user_id = user_id

        resource = _OwnedResource(owner_id)

        # Owner: must not raise.
        verify_resource_ownership(resource, owner_id, "file")

        # Any distinct user: must be denied with 403 Forbidden.
        with pytest.raises(HTTPException) as exc_info:
            verify_resource_ownership(resource, other_id, "file")
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @given(
        n_a=st.integers(min_value=1, max_value=6),
        n_b=st.integers(min_value=0, max_value=6),
    )
    @settings(max_examples=40, deadline=None)
    def test_get_resource_or_deny_enforces_ownership(self, n_a: int, n_b: int) -> None:
        """``get_resource_or_deny`` returns A's record to A but 403s to B.

        For every record owned by A, fetching it as A returns the record, while
        fetching the same record id as the distinct user B is denied with 403.

        Validates: Requirements 8.21
        """
        with fresh_session() as session:
            user_a = _make_user(session, f"a_{uuid.uuid4().hex}@example.com")
            user_b = _make_user(session, f"b_{uuid.uuid4().hex}@example.com")
            assume(user_a.id != user_b.id)

            _make_files(session, user_a, n_a, "a")
            _make_files(session, user_b, n_b, "b")

            a_files = session.execute(
                select(DataFile).where(DataFile.user_id == user_a.id)
            ).scalars().all()
            assert len(a_files) == n_a

            for record in a_files:
                # Owner A retrieves the record.
                returned = get_resource_or_deny(session, DataFile, record.id, user_a.id, "file")
                assert returned.id == record.id
                assert returned.user_id == user_a.id

                # Distinct user B is denied with 403 Forbidden.
                with pytest.raises(HTTPException) as exc_info:
                    get_resource_or_deny(session, DataFile, record.id, user_b.id, "file")
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestUserDataIsolationExamples:
    """Representative example-based regressions for Property 16 (Req 8.17-8.22)."""

    def test_scoped_query_returns_only_own_data(self) -> None:
        """A's scoped query returns only A's records, B's only B's (Req 8.18, 8.22)."""
        with fresh_session() as session:
            user_a = _make_user(session, "iso_a@example.com")
            user_b = _make_user(session, "iso_b@example.com")
            _make_files(session, user_a, 3, "a")
            _make_files(session, user_b, 2, "b")

            a_results = session.execute(
                get_user_scoped_query(select(DataFile), DataFile, user_a.id)
            ).scalars().all()
            b_results = session.execute(
                get_user_scoped_query(select(DataFile), DataFile, user_b.id)
            ).scalars().all()

            assert len(a_results) == 3
            assert all(f.user_id == user_a.id for f in a_results)
            assert len(b_results) == 2
            assert all(f.user_id == user_b.id for f in b_results)

    def test_scoped_query_empty_for_user_without_data(self) -> None:
        """A user with no records gets an empty scoped result (Req 8.18)."""
        with fresh_session() as session:
            user_a = _make_user(session, "empty_a@example.com")
            user_b = _make_user(session, "owns_b@example.com")
            _make_files(session, user_b, 4, "b")

            a_results = session.execute(
                get_user_scoped_query(select(DataFile), DataFile, user_a.id)
            ).scalars().all()
            assert a_results == []

    def test_cross_user_resource_access_denied(self) -> None:
        """Fetching another user's record by id is denied with 403 (Req 8.21)."""
        with fresh_session() as session:
            user_a = _make_user(session, "owner_a@example.com")
            user_b = _make_user(session, "intruder_b@example.com")
            _make_files(session, user_a, 1, "a")

            record = session.execute(
                select(DataFile).where(DataFile.user_id == user_a.id)
            ).scalars().one()

            # Owner can access.
            assert get_resource_or_deny(session, DataFile, record.id, user_a.id, "file").id == record.id

            # Other user is forbidden.
            with pytest.raises(HTTPException) as exc_info:
                get_resource_or_deny(session, DataFile, record.id, user_b.id, "file")
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_verify_ownership_404_for_missing_resource(self) -> None:
        """A missing (None) resource raises 404 before any ownership check (Req 8.21)."""
        with pytest.raises(HTTPException) as exc_info:
            verify_resource_ownership(None, uuid.uuid4(), "file")
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
