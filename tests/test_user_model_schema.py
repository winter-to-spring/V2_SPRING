import inspect
import uuid
from datetime import datetime
from sqlalchemy import UUID, String, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.schema import UniqueConstraint

# Import the User model
from test.service_backend.app.models.user import User


def test_user_model_exists():
    """Verify User model class exists and is importable."""
    assert User is not None
    assert hasattr(User, "__tablename__")


def test_user_table_name():
    """Verify User model has correct table name."""
    assert User.__tablename__ == "users"


def test_user_model_id_column():
    """Verify id column: UUID PK, default uuid4."""
    id_col = User.id
    assert id_col.primary_key
    assert id_col.type.__class__.__name__ == "UUID"
    assert id_col.default is not None
    # Verify default is uuid4
    default_callable = id_col.default.arg
    assert callable(default_callable)
    assert default_callable() == uuid.uuid4() or isinstance(
        default_callable(), uuid.UUID
    )


def test_user_model_email_column():
    """Verify email column: str unique not null."""
    email_col = User.email
    assert not email_col.nullable
    assert email_col.unique
    assert isinstance(email_col.type, String)


def test_user_model_hashed_password_column():
    """Verify hashed_password column: str nullable."""
    pwd_col = User.hashed_password
    assert pwd_col.nullable
    assert isinstance(pwd_col.type, String)


def test_user_model_name_column():
    """Verify name column: str nullable."""
    name_col = User.name
    assert name_col.nullable
    assert isinstance(name_col.type, String)


def test_user_model_created_at_column():
    """Verify created_at column: TIMESTAMPTZ default now()."""
    created_at_col = User.created_at
    assert isinstance(created_at_col.type, DateTime)
    assert created_at_col.type.timezone is True
    assert created_at_col.default is not None
    # Verify default uses sql.func.now()
    default_arg = created_at_col.default.arg
    assert hasattr(default_arg, "compile")  # SQLAlchemy expression


def test_user_model_updated_at_column():
    """Verify updated_at column: TIMESTAMPTZ."""
    updated_at_col = User.updated_at
    assert isinstance(updated_at_col.type, DateTime)
    assert updated_at_col.type.timezone is True


def test_user_model_has_all_columns():
    """Verify User model has all required columns."""
    required_columns = ["id", "email", "hashed_password", "name", "created_at", "updated_at"]
    for col_name in required_columns:
        assert hasattr(User, col_name), f"User model missing column: {col_name}"


def test_user_model_column_count():
    """Verify User model has exactly the expected columns."""
    expected_count = 6
    actual_columns = [
        col for col in dir(User)
        if not col.startswith("_") and hasattr(getattr(User, col), "type")
    ]
    assert len(actual_columns) == expected_count


def test_user_model_is_orm_base():
    """Verify User model inherits from proper ORM base."""
    assert hasattr(User, "__table__")
    assert hasattr(User, "__mapper__")
