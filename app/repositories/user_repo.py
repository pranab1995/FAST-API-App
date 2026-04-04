# =============================================================================
# app/repositories/user_repo.py
#
# PURPOSE:
#   The repository layer is the ONLY place that touches the database directly.
#   It contains raw query logic — no business rules, no password hashing,
#   just DB read/write operations.
#
# WHY A REPOSITORY LAYER?
#   1. Single Responsibility: DB queries are isolated here.
#      If you switch from SQLAlchemy to another ORM, only this file changes.
#   2. Testability: You can mock UserRepository in service tests without
#      a real database.
#   3. Reusability: Multiple services can call the same repo method.
#
# DRF EQUIVALENT:
#   DRF has no explicit repository layer. DB queries live directly in views
#   (get_queryset()) or serializer save methods. This is pragmatic for small
#   apps but becomes messy at scale. The repository pattern gives you a
#   clean seam for mocking and future ORM changes.
#
# WHAT BELONGS HERE:
#   ✅ db.query(...).filter(...).first()
#   ✅ db.add(model_instance)
#   ✅ db.commit() / db.refresh()
#   ✅ db.delete(model_instance)
#
# WHAT DOES NOT BELONG HERE:
#   ❌ Password hashing (→ security.py)
#   ❌ Token creation (→ security.py)
#   ❌ Business rules like "check if email already registered" (→ service)
#   ❌ HTTP exceptions (→ service or router layer)
# =============================================================================

from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """
    Data access layer for the User model.

    All methods receive a `db` (Session) parameter — the session is created
    per-request in the dependency and passed down through the call chain:

      Request → Router → Service → Repository(db)

    DRF EQUIVALENT:
      User.objects.get(pk=pk)   →  get_by_id(db, user_id)
      User.objects.create(...)  →  create(db, ...)
      user.save()               →  update(db, user, data)
      user.delete()             →  delete(db, user)
    """

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        """
        Fetch a user by primary key.

        Returns None if not found — callers decide whether to raise 404.
        """
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """
        Fetch a user by email address.

        Used during:
          - Login: check credentials
          - Registration: ensure email is not already taken
        """
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create(
        db: Session,
        email: str,
        full_name: str,
        hashed_password: str,
    ) -> User:
        """
        Persist a new User row and return the populated instance.

        Note: hashed_password is passed in (NOT plain password).
        Hashing happens in user_service.py before calling this method.

        db.refresh(user) re-reads the row from DB so auto-generated
        fields like `id` and `created_at` are populated on the object.
        """
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
        )
        db.add(user)
        db.commit()
        db.refresh(user)  # Populate server-generated fields (id, created_at)
        return user

    @staticmethod
    def update(db: Session, user: User, update_data: dict) -> User:
        """
        Apply a dict of changes to an existing User and persist them.

        `update_data` should only contain the fields explicitly sent by the
        client (None values are excluded by the service layer so we don't
        overwrite set fields with NULL).

        Equivalent to Django's User.objects.filter(pk=pk).update(**data)
        but returns the updated ORM instance instead of a row count.
        """
        for field, value in update_data.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete(db: Session, user: User) -> None:
        """
        Hard-delete a user from the database.

        In production you'd likely use a soft-delete (set is_active=False)
        to preserve audit history. This method is provided for completeness.
        """
        db.delete(user)
        db.commit()
