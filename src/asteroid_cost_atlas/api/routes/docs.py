"""Static documentation served via the API (markdown source)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/docs", tags=["docs"])


def _docs_root() -> Path:
    """Resolve the docs/ directory (repo root in dev, /app/docs in container)."""
    module = Path(__file__).resolve()
    for p in [module, *module.parents]:
        if (p / "pyproject.toml").exists():
            return p / "docs"
    return Path("/app/docs")


@router.get("/methodology")
def methodology() -> PlainTextResponse:
    """Raw markdown of the methodology document.

    Cached for 1 hour at the edge to avoid hitting the disk per pageview.
    """
    path = _docs_root() / "METHODOLOGY.md"
    if not path.exists():
        raise HTTPException(404, "Methodology document not found")
    return PlainTextResponse(
        content=path.read_text(encoding="utf-8"),
        headers={"Cache-Control": "public, max-age=3600"},
    )
