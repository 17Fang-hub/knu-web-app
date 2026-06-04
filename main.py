import csv
import io
import os
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from database import engine, AsyncSessionLocal, Base
from models import Image, ProcessingRun, DetectionResult
from processing import (
    preview_all,
    process_all,
    ALPHA_VALUES,
    SIGMA_OPTIONS,
)

# Legacy tables from the previous metrics design — removed during the refactor.
_LEGACY_TABLES = ["noise_robustness_tests", "processing_results"]


async def _run_migrations(conn) -> None:
    """Drop tables that belonged to the old (removed) metrics/IoU design."""
    for table_name in _LEGACY_TABLES:
        try:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        except Exception:
            pass


def _clamp_sigma(sigma: float) -> float:
    """Snap the requested σ to the nearest allowed option."""
    return min(SIGMA_OPTIONS, key=lambda s: abs(s - sigma))


UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PROCESSED_DIR = Path("static/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await _run_migrations(conn)
        await conn.run_sync(Base.metadata.create_all)

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


def _run_to_dict(run: ProcessingRun) -> dict:
    """Serialise a saved run (+ its per-α detections) for the frontend."""
    return {
        "id": run.id,
        "source_filename": run.source_filename,
        "sigma": run.sigma,
        "sobel": {
            "url": f"/static/processed/{run.sobel_filename}",
            "edge_density": run.sobel_edge_density,
            "time_ms": run.sobel_time_ms,
        },
        "alphas": [
            {
                "alpha": d.alpha,
                "url": f"/static/processed/{d.gl_filename}",
                "gl_edge_density": d.gl_edge_density,
                "gl_time_ms": d.gl_time_ms,
                "der": d.der,
                "dcr": d.dcr,
                "dcs": d.dcs,
            }
            for d in run.detections
        ],
    }


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Image).order_by(Image.uploaded_at.desc())
        )
        images = result.scalars().all()

        res = await session.execute(
            select(ProcessingRun)
            .options(selectinload(ProcessingRun.detections))
            .order_by(ProcessingRun.processed_at.desc())
        )
        runs = res.scalars().all()

        runs_data = {r.id: _run_to_dict(r) for r in runs}

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "images": images,
            "runs": runs,
            "runs_data": runs_data,
            "has_results": len(runs) > 0,
            "alpha_values": ALPHA_VALUES,
            "sigma_options": SIGMA_OPTIONS,
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
async def preview_image(filename: str, sigma: float = 0):
    """
    Quick preview (no DB/disk write) of both methods for the chosen σ:
    Sobel once + GL-Canny for every α in ALPHA_VALUES.
    """
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "Файл не знайдено"})

    payload = await run_in_threadpool(preview_all, file_path, _clamp_sigma(sigma))
    return JSONResponse(payload)


@app.post("/process/{filename}")
async def process_image(filename: str, sigma: float = 0):
    """
    Full processing for the chosen σ: Sobel once + GL-Canny per α. Each α is
    persisted as a DetectionResult row under one ProcessingRun.
    """
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "Файл не знайдено"})

    sig = _clamp_sigma(sigma)
    result = await run_in_threadpool(process_all, file_path, PROCESSED_DIR, sig)
    sobel = result["sobel"]

    async with AsyncSessionLocal() as session:
        run = ProcessingRun(
            source_filename=filename,
            sigma=sig,
            sobel_filename=sobel["filename"],
            sobel_edge_density=sobel["edge_density"],
            sobel_time_ms=sobel["time_ms"],
        )
        for row in result["alphas"]:
            run.detections.append(DetectionResult(
                alpha=row["alpha"],
                gl_filename=row["filename"],
                gl_edge_density=row["gl_edge_density"],
                gl_time_ms=row["gl_time_ms"],
                der=row["der"],
                dcr=row["dcr"],
                dcs=row["dcs"],
            ))
        session.add(run)
        await session.commit()

        await session.refresh(run, attribute_names=["detections"])
        payload = _run_to_dict(run)

    return JSONResponse(payload)


@app.delete("/result/{run_id}")
async def delete_result(run_id: int):
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ProcessingRun)
            .options(selectinload(ProcessingRun.detections))
            .where(ProcessingRun.id == run_id)
        )
        run = res.scalar_one_or_none()
        if not run:
            return JSONResponse(status_code=404, content={"error": "Запис не знайдено"})

        filenames = [run.sobel_filename] + [d.gl_filename for d in run.detections]
        for filename in filenames:
            p = PROCESSED_DIR / str(filename)
            if p.exists():
                os.remove(p)

        # Cascade removes the associated detection rows.
        await session.delete(run)
        await session.commit()

    return JSONResponse({"ok": True})


@app.get("/export-csv")
async def export_csv():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ProcessingRun)
            .options(selectinload(ProcessingRun.detections))
            .order_by(ProcessingRun.processed_at.desc())
        )
        runs = result.scalars().all()

    def _v(x):
        return "" if x is None else x

    output = io.StringIO()
    output.write('﻿')
    writer = csv.writer(output)

    # One row per (image, σ, α): comparison metrics + per-method density/time.
    writer.writerow([
        "Назва фото",
        "σ (шум)",
        "α (дробова)",
        "Edge density GL-Canny",
        "Час GL-Canny (мс)",
        "DER",
        "DCR",
        "DCS",
        "Edge density Sobel",
        "Час Sobel (мс)",
    ])

    for run in runs:
        for d in run.detections:
            writer.writerow([
                run.source_filename,
                _v(run.sigma),
                _v(d.alpha),
                _v(d.gl_edge_density),
                _v(d.gl_time_ms),
                _v(d.der),
                _v(d.dcr),
                _v(d.dcs),
                _v(run.sobel_edge_density),
                _v(run.sobel_time_ms),
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )
