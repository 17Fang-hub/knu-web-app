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
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from database import engine, AsyncSessionLocal, Base
from models import Image, ProcessingResult
from processing import process_both, fractional_preview, sobel_preview, DEFAULT_ALPHA

ALPHA_MIN, ALPHA_MAX = 0.1, 1.9


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
            select(ProcessingResult).order_by(ProcessingResult.processed_at.desc())
        )
        results = res.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "images": images,
            "results": results,
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
    Швидке превʼю (без запису в БД/на диск). Дробовий метод рахується завжди
    (для повзунка α); Sobel — лише за with_sobel=true (при відкритті вікна).
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

    async with AsyncSessionLocal() as session:
        record = ProcessingResult(
            source_filename=filename,
            fractional_filename=result["classical"]["filename"],
            fractional_time_ms=result["classical"]["time_ms"],
            fractional_snr=result["classical"]["snr"],
            fractional_alpha=result["classical"]["alpha"],
            sobel_filename=result["secondary"]["filename"],
            sobel_time_ms=result["secondary"]["time_ms"],
            sobel_snr=result["secondary"]["snr"],
        )
        session.add(record)
        await session.commit()

    return JSONResponse({
        "id": record.id,
        "classical": {
            "url": f"/static/processed/{result['classical']['filename']}",
            "time_ms": result["classical"]["time_ms"],
            "snr": result["classical"]["snr"],
            "alpha": result["classical"]["alpha"],
        },
        "secondary": {
            "url": f"/static/processed/{result['secondary']['filename']}",
            "time_ms": result["secondary"]["time_ms"],
            "snr": result["secondary"]["snr"],
        },
    })


@app.delete("/result/{result_id}")
async def delete_result(result_id: int):
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ProcessingResult).where(ProcessingResult.id == result_id)
        )
        record = res.scalar_one_or_none()
        if not record:
            return JSONResponse(status_code=404, content={"error": "Запис не знайдено"})

        for filename in (record.fractional_filename, record.sobel_filename):
            p = PROCESSED_DIR / filename
            if p.exists():
                os.remove(p)

        await session.delete(record)
        await session.commit()

    return JSONResponse({"ok": True})


@app.get("/export-csv")
async def export_csv():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ProcessingResult).order_by(ProcessingResult.processed_at.desc())
        )
        records = result.scalars().all()

    output = io.StringIO()
    output.write('﻿')
    writer = csv.writer(output)
    writer.writerow([
        "Назва фото",
        "α (дробова)",
        "Час Дробовий (мс)", "SNR Дробовий",
        "Час Sobel (мс)", "SNR Sobel",
        "Дата обробки",
    ])
    for r in records:
        writer.writerow([
            r.source_filename,
            r.fractional_alpha if r.fractional_alpha is not None else "",
            r.fractional_time_ms,
            r.fractional_snr,
            r.sobel_time_ms,
            r.sobel_snr,
            r.processed_at.strftime("%Y-%m-%d %H:%M:%S") if r.processed_at is not None else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )
