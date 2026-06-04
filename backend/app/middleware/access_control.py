"""Data access control utilities for user data isolation.

Provides helpers to enforce that all database queries are scoped to the
authenticated user, and that cross-user access is denied with 403 Forbidden.
Requirements: 8.17-8.22
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select
from sqlalchemy.orm import Session


def get_user_scoped_query(query: Select, model, user_id: uuid.UUID) -> Select:
    """Add user_id filter to a SQLAlchemy Select query for data isolation.

    This ensures all data queries are automatically scoped to the authenticated
    user, enforcing data isolation at the database query level (Req 8.22).

    Args:
        query: An existing SQLAlchemy Select statement.
        model: The SQLAlchemy model class that has a `user_id` column.
        user_id: The authenticated user's UUID.

    Returns:
        The query with an additional WHERE clause filtering by user_id.

    Example:
        query = select(DataFile)
        scoped_query = get_user_scoped_query(query, DataFile, current_user.id)
        results = db.execute(scoped_query).scalars().all()
    """
    return query.where(model.user_id == user_id)


def verify_resource_ownership(
    resource,
    user_id: uuid.UUID,
    resource_name: str = "resource",
) -> None:
    """Verify that a resource belongs to the specified user.

    Checks the resource's user_id attribute against the provided user_id.
    If they don't match, raises 403 Forbidden (Req 8.21).

    Args:
        resource: A SQLAlchemy model instance with a `user_id` attribute.
        user_id: The authenticated user's UUID.
        resource_name: Human-readable name for error messages.

    Raises:
        HTTPException 403: If the resource does not belong to the user.
        HTTPException 404: If the resource is None.
    """
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} not found",
        )

    if resource.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: you do not have permission to access this {resource_name}",
        )


def get_resource_or_deny(
    db: Session,
    model,
    resource_id: uuid.UUID,
    user_id: uuid.UUID,
    resource_name: str = "resource",
):
    """Load a resource by ID and verify ownership in one step.

    Combines fetching a resource and verifying ownership. This is the
    recommended pattern for endpoints that access a specific resource by ID
    (Req 8.20, 8.21).

    Args:
        db: SQLAlchemy database session.
        model: The SQLAlchemy model class.
        resource_id: The UUID of the resource to load.
        user_id: The authenticated user's UUID.
        resource_name: Human-readable name for error messages.

    Returns:
        The resource instance if it exists and belongs to the user.

    Raises:
        HTTPException 404: If the resource does not exist.
        HTTPException 403: If the resource belongs to another user.
    """
    from sqlalchemy import select

    resource = db.execute(
        select(model).where(model.id == resource_id)
    ).scalar_one_or_none()

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} not found",
        )

    if resource.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: you do not have permission to access this {resource_name}",
        )

    return resource
