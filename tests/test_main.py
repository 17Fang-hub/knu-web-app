import pytest
import pytest_asyncio
import cv2
import numpy as np
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database import Base
from models import Image
import main

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    main.AsyncSessionLocal = test_db

    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test"
    ) as c:
        yield c


def _make_jpeg() -> bytes:
    img = np.zeros((60, 60, 3), dtype=np.uint8)
    img[10:50, 10:50] = 200
    _, buf = cv2.imencode(".jpg", img)
    return bytes(buf)


# ── existing tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_homapage_returns_200(client):
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_valid_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    image_data = b"fake image content"
    response = await client.post(
        "/upload",
        files={"file": ("test_image.jpg", image_data, "image/jpeg")}
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_upload_duplicate_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    image_data = b"fake image content"
    files = {"file": ("duplicate.jpg", image_data, "imgae/jpeg")}

    await client.post("/upload", files=files)

    files = {"file": ("duplicate.jpg", image_data, "image/jpeg")}
    response = await client.post("/upload", files=files)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_existing_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    image_data = b"fake image content"
    await client.post(
        "/upload",
        files={"file": ("to_delete.jpg", image_data, "image/jpeg")}
    )

    response = await client.delete("/delete/to_delete.jpg")
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_delete_nonexistent_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    response = await client.delete("/delete/ghost.jpg")
    assert response.status_code == 303


# ── new tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("proc_test.jpg", _make_jpeg(), "image/jpeg")}
    )

    response = await client.post("/process/proc_test.jpg")
    assert response.status_code == 200
    data = response.json()
    assert "classical" in data
    assert "secondary" in data
    assert "url" in data["classical"]
    assert "time_ms" in data["classical"]
    assert "snr" in data["classical"]


@pytest.mark.asyncio
async def test_process_nonexistent_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    main.PROCESSED_DIR = tmp_path / "processed"
    main.PROCESSED_DIR.mkdir()

    response = await client.post("/process/ghost.jpg")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_csv_empty(client):
    response = await client.get("/export-csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_export_csv_with_data(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("csv_test.jpg", _make_jpeg(), "image/jpeg")}
    )
    await client.post("/process/csv_test.jpg")

    response = await client.get("/export-csv")
    assert response.status_code == 200
    content = response.text
    assert "csv_test.jpg" in content
