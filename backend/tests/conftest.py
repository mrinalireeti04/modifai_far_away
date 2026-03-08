"""
Shared fixtures for all backend tests.

Uses an in-memory SQLite database (via aiosqlite) for isolation,
and patches AWSService methods to avoid real AWS calls.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.base import Base
from app.database import get_db
from app.main import app


# ── Async event loop ───────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── In-memory SQLite engine ───────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # SQLite doesn't handle SQLAlchemy Enum natively — render as VARCHAR
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── Session fixture ────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_session(db_engine):
    session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


# ── Override the get_db dependency ─────────────────────────────────────────────
@pytest_asyncio.fixture
async def client(db_engine):
    session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── AWS Service mocks ─────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def mock_aws_service():
    """Patch all AWSService static/class methods to avoid real AWS calls.
    
    Only evaluate_text_sample is async; all others are sync @staticmethod.
    """
    with patch.multiple(
        "app.services.aws_service.AWSService",
        generate_presigned_url=MagicMock(return_value="https://s3.example.com/upload?sig=abc"),
        start_pipeline_execution=MagicMock(
            return_value="arn:aws:states:us-east-1:123456:execution:Pipeline:run-1"
        ),
        get_pipeline_status=MagicMock(return_value={
            "status": "RUNNING",
        }),
        get_execution_history=MagicMock(return_value=[
            {
                "id": "1",
                "timestamp": "2026-03-08T10:00:00.000Z",
                "type": "ExecutionStarted",
                "details": {"name": "Pipeline"},
            }
        ]),
        evaluate_text_sample=AsyncMock(return_value={
            "score": 0.85,
            "explanation": "The text is well-structured and relevant to the intent.",
        }),
        get_generated_dataset=MagicMock(return_value=[
            {"instruction": "What is AI?", "response": "AI is artificial intelligence.", "confidence": 0.9},
            {"instruction": "Explain ML", "response": "ML is machine learning.", "confidence": 0.8},
        ]),
        generate_presigned_get_url=MagicMock(return_value="https://s3.example.com/download?sig=xyz"),
        get_execution_output=MagicMock(return_value={
            "status": "SUCCEEDED",
            "output": {
                "dataset_s3_key": "projects/test/output/dataset.jsonl",
                "model_endpoint": "https://sagemaker.example.com/endpoint/test",
                "training_metrics": {"final_loss": 0.12, "duration_min": 45},
                "step_results": {},
            }
        }),
        update_dataset_example=MagicMock(return_value={
            "instruction": "Updated", "response": "Updated response", "confidence": 0.9
        }),
        delete_dataset_example=MagicMock(return_value=None),
        search_dataset=MagicMock(return_value=[
            {"instruction": "What is AI?", "response": "AI is artificial intelligence.", "confidence": 0.9},
        ]),
        get_dataset_export_url=MagicMock(return_value="https://s3.example.com/export?sig=export"),
        delete_s3_prefix=MagicMock(return_value=None),
        invoke_base_model=MagicMock(return_value={
            "response": "Machine learning is a subset of AI that enables systems to learn from data.",
        }),
        invoke_sagemaker_endpoint=MagicMock(return_value={
            "response": "ML is a method of data analysis that automates analytical model building.",
        }),
    ):
        yield
