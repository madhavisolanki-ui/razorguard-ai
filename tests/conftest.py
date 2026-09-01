"""Shared Pytest Fixtures for RazorGuard AI."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.database import Base
from src.database.repository import Repository
from src.generator.profiles import SyntheticProfilePool
from src.generator.scenarios import ScenarioGenerator
from src.generator.stream_simulator import StreamSimulator


@pytest.fixture(scope="session")
def test_engine():
    """In-memory SQLite database engine for fast isolated testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Provides a transactional database session per test function."""
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def repository(db_session):
    """Provides an initialized repository instance."""
    return Repository(db_session)


@pytest.fixture(scope="session")
def profile_pool():
    """Provides pre-seeded synthetic profile pool."""
    return SyntheticProfilePool(pool_size=100, seed=123)


@pytest.fixture(scope="session")
def scenario_generator(profile_pool):
    """Provides a ScenarioGenerator instance."""
    return ScenarioGenerator(profile_pool=profile_pool, seed=123)


@pytest.fixture(scope="session")
def stream_simulator():
    """Provides a StreamSimulator instance."""
    return StreamSimulator(seed=123)
