from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

def mount_workstation(app: FastAPI, *, repository_root: Path | None = None) -> bool:
    root = repository_root or Path(__file__).resolve().parents[3]
    dist = root / "ui" / "workstation" / "dist"
    if not (dist / "index.html").is_file():
        return False
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="m41-assets")
    @app.get("/{full_path:path}", include_in_schema=False)
    async def m41_spa(full_path: str):
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
    return True
