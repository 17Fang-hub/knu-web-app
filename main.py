import shutil
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from database import engine, AsyncSessionLocal, Base
from models import Image
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Image).order_by(Image.uploaded_at.desc())
        )
        images = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"images": images}
    )

@app.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    filename=file.filename or "image.jpg"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    async with AsyncSessionLocal() as session:
        new_image = Image(filename=filename)
        session.add(new_image)
        await session.commit()

    return RedirectResponse(url="/", status_code=303)