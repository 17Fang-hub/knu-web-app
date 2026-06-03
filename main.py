import csv
import io
import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile, File, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from database import engine, AsyncSessionLocal, Base
from models import Image, ProcessingResult, NoiseRobustnessTest
from processing import (
    process_both,
    fractional_preview,
    sobel_preview,
    noise_robustness,
    DEFAULT_ALPHA,
    NOISE_SIGMAS,
)

ALPHA_MIN, ALPHA_MAX = 0.1, 1.9

_NEW_COLUMNS = [
    ("processing_results",      "fractional_edge_density",          "REAL"),
    ("processing_results",      "fractional_mean_edge_strength",     "REAL"),
    ("processing_results",      "fractional_num_components",         "INTEGER"),
    ("processing_results",      "fractional_mean_component_length",  "REAL"),
    ("processing_results",      "fractional_fragmentation",          "REAL"),
    ("processing_results",      "fractional_contrast_ratio",         "REAL"),
    ("processing_results",      "sobel_edge_density",               "REAL"),
    ("processing_results",      "sobel_mean_edge_strength",          "REAL"),
    ("processing_results",      "sobel_num_components",             "INTEGER"),
    ("processing_results",      "sobel_mean_component_length",       "REAL"),
    ("processing_results",      "sobel_fragmentation",              "REAL"),
    ("processing_results",      "sobel_contrast_ratio",             "REAL"),
]


async def _run_migrations(conn) -> None:
    """Idempotently add new columns to existing tables."""
    for table_name, col_name, col_type in _NEW_COLUMNS:
        try:
            await conn.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                )
            )
        except Exception:
            pass


def _clamp_alpha(alpha: float) -> float:
    return max(ALPHA_MIN, min(ALPHA_MAX, alpha))


UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PROCESSED_DIR = Path("static/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Image))
        db_images = {str(img.filename) for img in result.scalars().all()}

        disk_images = {
            f.name for f in UPLOAD_DIR.iterdir()
            if f.is_file()
        }

        for filename in disk_images - db_images:
            session.add(Image(filename=filename))

        for filename in db_images - disk_images:
            result = await session.execute(
                select(Image).where(Image.filename == filename)
            )
            images_to_delete = result.scalars().all()
            for image in images_to_delete:
                await session.delete(image)

        await session.commit()
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Image).order_by(Image.uploaded_at.desc())
        )
        images = result.scalars().all()

        res = await session.execute(
            select(ProcessingResult)
            .options(selectinload(ProcessingResult.noise_tests))
            .order_by(ProcessingResult.processed_at.desc())
        )
        results = res.scalars().all()

        # Per-result noise-robustness chart data (None when no test was saved).
        noise_by_result = {}
        for r in results:
            tests = r.noise_tests
            if tests:
                noise_by_result[r.id] = {
                    "noise_levels": [t.noise_sigma for t in tests],
                    "sobel_iou": [t.sobel_iou for t in tests],
                    "gl_canny_iou": [t.gl_canny_iou for t in tests],
                    "alpha": r.fractional_alpha,
                }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "images": images,
            "results": results,
            "noise_by_result": noise_by_result,
            "has_results": len(results) > 0,
        }
    )


@app.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    filename = file.filename or "image.jpg"
    file_path = UPLOAD_DIR / filename

    async with AsyncSessionLocal() as session:
        try:
            new_image = Image(filename=filename)
            session.add(new_image)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return JSONResponse(
                status_code=409,
                content={"error": f"Зображення з назвою '{filename}' вже існує."}
            )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return RedirectResponse(url="/", status_code=303)


@app.delete("/delete/{filename}")
async def delete_image(filename: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Image).where(Image.filename == filename)
        )
        image = result.scalar_one_or_none()
        if image:
            await session.delete(image)
            await session.commit()

    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        os.remove(file_path)

    return RedirectResponse(url="/", status_code=303)


@app.post("/preview/{filename}")
async def preview_image(filename: str, alpha: float = DEFAULT_ALPHA, with_sobel: bool = False):
    """
    Quick preview (no DB/disk write). Fractional method is always computed
    (for the alpha slider); Sobel only when with_sobel=true (on modal open).
    """
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "Файл не знайдено"})

    payload = {
        "fractional": fractional_preview(file_path, alpha=_clamp_alpha(alpha)),
        "sobel": sobel_preview(file_path) if with_sobel else None,
    }
    return JSONResponse(payload)


@app.post("/process/{filename}")
async def process_image(filename: str, alpha: float = DEFAULT_ALPHA):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "Файл не знайдено"})

    result = process_both(file_path, PROCESSED_DIR, alpha=_clamp_alpha(alpha))
    cl = result["classical"]
    sc = result["secondary"]

    async with AsyncSessionLocal() as session:
        record = ProcessingResult(
            source_filename=filename,
            fractional_filename=cl["filename"],
            fractional_time_ms=cl["time_ms"],
            fractional_alpha=cl["alpha"],
            fractional_edge_density=cl["edge_density"],
            fractional_mean_edge_strength=cl["mean_edge_strength"],
            fractional_num_components=cl["num_components"],
            fractional_mean_component_length=cl["mean_component_length"],
            fractional_fragmentation=cl["fragmentation"],
            fractional_contrast_ratio=cl["contrast_ratio"],
            sobel_filename=sc["filename"],
            sobel_time_ms=sc["time_ms"],
            sobel_edge_density=sc["edge_density"],
            sobel_mean_edge_strength=sc["mean_edge_strength"],
            sobel_num_components=sc["num_components"],
            sobel_mean_component_length=sc["mean_component_length"],
            sobel_fragmentation=sc["fragmentation"],
            sobel_contrast_ratio=sc["contrast_ratio"],
        )
        session.add(record)
        await session.commit()

    return JSONResponse({
        "id": record.id,
        "classical": {
            "url": f"/static/processed/{cl['filename']}",
            "time_ms": cl["time_ms"],
            "alpha": cl["alpha"],
            "edge_density": cl["edge_density"],
            "mean_edge_strength": cl["mean_edge_strength"],
            "num_components": cl["num_components"],
            "mean_component_length": cl["mean_component_length"],
            "fragmentation": cl["fragmentation"],
            "contrast_ratio": cl["contrast_ratio"],
        },
        "secondary": {
            "url": f"/static/processed/{sc['filename']}",
            "time_ms": sc["time_ms"],
            "edge_density": sc["edge_density"],
            "mean_edge_strength": sc["mean_edge_strength"],
            "num_components": sc["num_components"],
            "mean_component_length": sc["mean_component_length"],
            "fragmentation": sc["fragmentation"],
            "contrast_ratio": sc["contrast_ratio"],
        },
    })


@app.post("/analyze/noise-robustness/{filename}")
async def analyze_noise_robustness(filename: str, alpha: float = DEFAULT_ALPHA):
    """
    Preview-only noise-robustness battery (no DB write). The result is persisted
    only later, together with the processed pair, via POST /result/{id}/noise.
    """
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "Файл не знайдено"})

    result = await run_in_threadpool(noise_robustness, file_path, _clamp_alpha(alpha))
    return JSONResponse(result)


@app.post("/result/{result_id}/noise")
async def save_noise_robustness(result_id: int, payload: dict = Body(...)):
    """Persist a previously computed noise-robustness test against a saved pair."""
    levels = payload.get("noise_levels") or []
    sobel = payload.get("sobel_iou") or []
    gl = payload.get("gl_canny_iou") or []
    if not (len(levels) == len(sobel) == len(gl)) or not levels:
        return JSONResponse(status_code=400, content={"error": "Некоректні дані тесту"})

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ProcessingResult)
            .options(selectinload(ProcessingResult.noise_tests))
            .where(ProcessingResult.id == result_id)
        )
        record = res.scalar_one_or_none()
        if not record:
            return JSONResponse(status_code=404, content={"error": "Запис не знайдено"})

        # Replace any previously stored test for this pair.
        record.noise_tests.clear()
        for level, s_iou, g_iou in zip(levels, sobel, gl):
            record.noise_tests.append(NoiseRobustnessTest(
                noise_sigma=float(level),
                sobel_iou=float(s_iou),
                gl_canny_iou=float(g_iou),
            ))
        await session.commit()

    return JSONResponse({"ok": True})


@app.delete("/result/{result_id}")
async def delete_result(result_id: int):
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ProcessingResult)
            .options(selectinload(ProcessingResult.noise_tests))
            .where(ProcessingResult.id == result_id)
        )
        record = res.scalar_one_or_none()
        if not record:
            return JSONResponse(status_code=404, content={"error": "Запис не знайдено"})

        for filename in (record.fractional_filename, record.sobel_filename):
            p = PROCESSED_DIR / str(filename)
            if p.exists():
                os.remove(p)

        # Cascade removes the associated noise-robustness rows.
        await session.delete(record)
        await session.commit()

    return JSONResponse({"ok": True})


@app.get("/export-csv")
async def export_csv():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ProcessingResult)
            .options(selectinload(ProcessingResult.noise_tests))
            .order_by(ProcessingResult.processed_at.desc())
        )
        records = result.scalars().all()

    def _v(x):
        return "" if x is None else x

    output = io.StringIO()
    output.write('﻿')
    writer = csv.writer(output)

    # Only the essentials: comparison metrics + noise-robustness IoU per σ.
    header = [
        "Назва фото",
        "α (дробова)",
        "Edge density GL-Canny",
        "Mean edge strength GL-Canny",
        "Кількість компонент GL-Canny",
        "Середня довжина GL-Canny (px)",
        "Фрагментація GL-Canny",
        "Контрастність GL-Canny",
        "Edge density Sobel",
        "Mean edge strength Sobel",
        "Кількість компонент Sobel",
        "Середня довжина Sobel (px)",
        "Фрагментація Sobel",
        "Контрастність Sobel",
    ]
    header += [f"IoU GL-Canny (σ={int(s)})" for s in NOISE_SIGMAS]
    header += [f"IoU Sobel (σ={int(s)})" for s in NOISE_SIGMAS]
    writer.writerow(header)

    for r in records:
        # Map σ → IoU for whichever robustness test (if any) was saved.
        gl_by_sigma = {round(t.noise_sigma): t.gl_canny_iou for t in r.noise_tests}
        sobel_by_sigma = {round(t.noise_sigma): t.sobel_iou for t in r.noise_tests}

        row = [
            r.source_filename,
            _v(r.fractional_alpha),
            _v(r.fractional_edge_density),
            _v(r.fractional_mean_edge_strength),
            _v(r.fractional_num_components),
            _v(r.fractional_mean_component_length),
            _v(r.fractional_fragmentation),
            _v(r.fractional_contrast_ratio),
            _v(r.sobel_edge_density),
            _v(r.sobel_mean_edge_strength),
            _v(r.sobel_num_components),
            _v(r.sobel_mean_component_length),
            _v(r.sobel_fragmentation),
            _v(r.sobel_contrast_ratio),
        ]
        row += [_v(gl_by_sigma.get(round(s))) for s in NOISE_SIGMAS]
        row += [_v(sobel_by_sigma.get(round(s))) for s in NOISE_SIGMAS]
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )
