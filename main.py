import shutil
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    images = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]

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

    return RedirectResponse(url="/", status_code=303)