import pytest
import pytest_asyncio
import cv2
import numpy as np
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from database import Base
from models import Image, ProcessingResult, NoiseRobustnessTest
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
    assert "alpha" in data["classical"]
    assert "edge_density" in data["classical"]
    assert "mean_edge_strength" in data["classical"]
    assert "num_components" in data["classical"]
    assert "edge_density" in data["secondary"]


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
    assert "Edge density GL-Canny" in content


# ── preview (повзунок α) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_with_sobel(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    await client.post(
        "/upload",
        files={"file": ("prev.jpg", _make_jpeg(), "image/jpeg")}
    )

    response = await client.post("/preview/prev.jpg?alpha=0.5&with_sobel=true")
    assert response.status_code == 200
    data = response.json()
    assert data["fractional"]["data_url"].startswith("data:image/jpeg;base64,")
    assert data["fractional"]["alpha"] == 0.5
    assert data["sobel"] is not None
    assert data["sobel"]["data_url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_preview_fractional_only(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    await client.post(
        "/upload",
        files={"file": ("prev2.jpg", _make_jpeg(), "image/jpeg")}
    )

    response = await client.post("/preview/prev2.jpg?alpha=1.2")
    assert response.status_code == 200
    data = response.json()
    assert data["fractional"]["alpha"] == 1.2
    assert data["sobel"] is None


@pytest.mark.asyncio
async def test_preview_alpha_clamped(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    await client.post(
        "/upload",
        files={"file": ("prev3.jpg", _make_jpeg(), "image/jpeg")}
    )

    high = await client.post("/preview/prev3.jpg?alpha=5.0")
    low = await client.post("/preview/prev3.jpg?alpha=0.0")
    assert high.json()["fractional"]["alpha"] == 1.9
    assert low.json()["fractional"]["alpha"] == 0.1


@pytest.mark.asyncio
async def test_preview_nonexistent_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    response = await client.post("/preview/ghost.jpg?alpha=0.5")
    assert response.status_code == 404


# ── noise robustness (Етап 2) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_noise_robustness(client, tmp_path):
    main.UPLOAD_DIR = tmp_path

    await client.post(
        "/upload",
        files={"file": ("noise_test.jpg", _make_jpeg(), "image/jpeg")}
    )

    response = await client.post("/analyze/noise-robustness/noise_test.jpg?alpha=0.5")
    assert response.status_code == 200
    data = response.json()
    assert data["noise_levels"] == [5.0, 10.0, 15.0, 20.0, 25.0]
    assert len(data["sobel_iou"]) == 5
    assert len(data["gl_canny_iou"]) == 5
    assert data["alpha"] == 0.5
    # IoU values must lie in [0, 1]
    for v in data["sobel_iou"] + data["gl_canny_iou"]:
        assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_noise_robustness_nonexistent_image(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    response = await client.post("/analyze/noise-robustness/ghost.jpg")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_noise_preview_does_not_persist(client, tmp_path, test_db):
    """The analyze endpoint is preview-only — nothing is written to the DB."""
    main.UPLOAD_DIR = tmp_path
    await client.post(
        "/upload",
        files={"file": ("np.jpg", _make_jpeg(), "image/jpeg")}
    )
    await client.post("/analyze/noise-robustness/np.jpg?alpha=0.5")

    async with test_db() as session:
        count = await session.scalar(select(func.count()).select_from(NoiseRobustnessTest))
    assert count == 0


@pytest.mark.asyncio
async def test_noise_saved_with_pair_and_cascade_delete(client, tmp_path, test_db):
    """Noise rows are persisted against a saved pair and removed with it."""
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("pair.jpg", _make_jpeg(), "image/jpeg")}
    )

    # Save the processed pair.
    proc = await client.post("/process/pair.jpg?alpha=0.5")
    result_id = proc.json()["id"]

    # Compute the noise test (preview) and persist it against the pair.
    noise = (await client.post("/analyze/noise-robustness/pair.jpg?alpha=0.5")).json()
    save = await client.post(f"/result/{result_id}/noise", json=noise)
    assert save.status_code == 200

    async with test_db() as session:
        count = await session.scalar(select(func.count()).select_from(NoiseRobustnessTest))
    assert count == 5

    # Deleting the pair cascades to the noise rows.
    await client.delete(f"/result/{result_id}")

    async with test_db() as session:
        remaining = await session.scalar(select(func.count()).select_from(NoiseRobustnessTest))
        results = await session.scalar(select(func.count()).select_from(ProcessingResult))
    assert remaining == 0
    assert results == 0


@pytest.mark.asyncio
async def test_save_noise_nonexistent_result(client):
    payload = {"noise_levels": [5.0], "sobel_iou": [0.5], "gl_canny_iou": [0.6]}
    response = await client.post("/result/9999/noise", json=payload)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_process_saves_alpha_in_csv(client, tmp_path):
    main.UPLOAD_DIR = tmp_path
    processed = tmp_path / "processed"
    processed.mkdir()
    main.PROCESSED_DIR = processed

    await client.post(
        "/upload",
        files={"file": ("alpha_test.jpg", _make_jpeg(), "image/jpeg")}
    )
    await client.post("/process/alpha_test.jpg?alpha=0.8")

    response = await client.get("/export-csv")
    content = response.text
    assert "α (дробова)" in content
    assert "0.8" in content
