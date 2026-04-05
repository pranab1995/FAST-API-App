import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_session
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
from typing import Generator

from app.main import app
from app.db.base import Base
from app.core.dependencies import get_db

# Use an in-memory SQLite database for fast isolated testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Create all tables in the test database
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup after all tests are done
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    # Override get_db dependency to use our test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    # Clear overrides after the test
    app.dependency_overrides.clear()
