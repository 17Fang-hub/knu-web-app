import pytest
import pytest_asyncio
import cv2
import numpy as np
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from database import Base
from models import Image, ProcessingRun, DetectionResult
from processing import ALPHA_VALUES, SIGMA_OPTIONS
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


# ── basic pages / upload / delete ───────────────────────────────────────────────

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


# ── processing: Sobel once + GL-Canny per α ──────────────────────────────────────

@pytest.mark.asyncio
async def test_process_image_returns_all_alphas(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("proc_test.jpg", _make_jpeg(), "image/jpeg")}
    )

    response = await client.post("/process/proc_test.jpg?sigma=0")
    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert data["sigma"] == 0
    assert "url" in data["sobel"]
    assert "edge_density" in data["sobel"]
    assert "time_ms" in data["sobel"]

    assert len(data["alphas"]) == len(ALPHA_VALUES)
    first = data["alphas"][0]
    for key in ("alpha", "url", "gl_edge_density", "gl_time_ms", "der", "dcr", "dcs"):
        assert key in first


@pytest.mark.asyncio
async def test_process_persists_one_row_per_alpha(client, tmp_path, test_db):
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("rows.jpg", _make_jpeg(), "image/jpeg")}
    )
    await client.post("/process/rows.jpg?sigma=10")

    async with test_db() as session:
        runs = await session.scalar(select(func.count()).select_from(ProcessingRun))
        detections = await session.scalar(select(func.count()).select_from(DetectionResult))
    assert runs == 1
    assert detections == len(ALPHA_VALUES)


@pytest.mark.asyncio
async def test_process_nonexistent_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    main.PROCESSED_DIR = tmp_path / "processed"
    main.PROCESSED_DIR.mkdir()

    response = await client.post("/process/ghost.jpg")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_alpha_one_close_to_sobel(client, tmp_path):
    """Вбудована перевірка: при α=1 GL-Canny має бути близьким до Sobel (DCS вищий)."""
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("a1.jpg", _make_jpeg(), "image/jpeg")}
    )
    data = (await client.post("/process/a1.jpg?sigma=0")).json()

    by_alpha = {round(a["alpha"], 1): a for a in data["alphas"]}
    assert 1.0 in by_alpha
    low = by_alpha[0.1]["dcs"]
    one = by_alpha[1.0]["dcs"]
    # α=1 повинно давати не гірший збіг із Sobel, ніж дуже мале α.
    assert one >= low


# ── delete run cascades to detections ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_run_cascades(client, tmp_path, test_db):
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("del.jpg", _make_jpeg(), "image/jpeg")}
    )
    run_id = (await client.post("/process/del.jpg?sigma=0")).json()["id"]

    resp = await client.delete(f"/result/{run_id}")
    assert resp.status_code == 200

    async with test_db() as session:
        runs = await session.scalar(select(func.count()).select_from(ProcessingRun))
        detections = await session.scalar(select(func.count()).select_from(DetectionResult))
    assert runs == 0
    assert detections == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_run(client):
    response = await client.delete("/result/9999")
    assert response.status_code == 404


# ── preview (no DB write) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_returns_sobel_and_alphas(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    await client.post(
        "/upload",
        files={"file": ("prev.jpg", _make_jpeg(), "image/jpeg")}
    )

    response = await client.post("/preview/prev.jpg?sigma=0")
    assert response.status_code == 200
    data = response.json()
    assert data["sobel"]["data_url"].startswith("data:image/jpeg;base64,")
    assert len(data["alphas"]) == len(ALPHA_VALUES)
    assert data["alphas"][0]["data_url"].startswith("data:image/jpeg;base64,")
    assert "der" in data["alphas"][0]


@pytest.mark.asyncio
async def test_preview_does_not_persist(client, tmp_path, test_db):
    main.UPLOAD_DIR = tmp_path
    await client.post(
        "/upload",
        files={"file": ("np.jpg", _make_jpeg(), "image/jpeg")}
    )
    await client.post("/preview/np.jpg?sigma=10")

    async with test_db() as session:
        count = await session.scalar(select(func.count()).select_from(ProcessingRun))
    assert count == 0


@pytest.mark.asyncio
async def test_preview_sigma_clamped(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    await client.post(
        "/upload",
        files={"file": ("prev2.jpg", _make_jpeg(), "image/jpeg")}
    )
    # 7 → найближче дозволене значення серед SIGMA_OPTIONS (5)
    response = await client.post("/preview/prev2.jpg?sigma=7")
    assert response.status_code == 200
    assert response.json()["sigma"] == 5
    assert 5 in SIGMA_OPTIONS


@pytest.mark.asyncio
async def test_preview_nonexistent_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    response = await client.post("/preview/ghost.jpg?sigma=0")
    assert response.status_code == 404


# ── CSV export ─────────────────────────────────────────────────────────────────

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
    await client.post("/process/csv_test.jpg?sigma=5")

    response = await client.get("/export-csv")
    assert response.status_code == 200
    content = response.text
    assert "csv_test.jpg" in content
    assert "Edge density GL-Canny" in content
    assert "DER" in content
    assert "σ (шум)" in content
