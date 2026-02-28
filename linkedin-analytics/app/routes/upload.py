"""File upload routes: upload form page and POST handler."""

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.ingest import DuplicateFileError, IngestError, ingest_file
from app.models import Upload

# Chunk size for streaming reads (1 MiB)
_CHUNK_SIZE = 1024 * 1024

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/upload", response_class=HTMLResponse)
async def upload_form(
    request: Request,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the file upload form with upload history."""
    uploads = (
        db.query(Upload)
        .order_by(desc(Upload.upload_date))
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "uploads": uploads,
            "flash": None,
            "flash_type": None,
        },
    )


@router.post("/upload")
async def handle_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """Handle file upload, parse the LinkedIn export, and load data to DB.

    On success, redirects to /dashboard.
    On duplicate, renders upload page with a warning.
    On other errors, renders upload page with an error message.
    """
    # Ensure uploads directory exists
    uploads_dir = settings.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Validate content type at the boundary
    if file.content_type not in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "application/octet-stream",  # Some browsers send this for .xlsx
    }:
        logger.warning("Rejected upload with content type: %s", file.content_type)
        # We let the ingest validator catch extension errors for better UX

    # Save the file to a temporary location before validation.
    # Enforce the size limit at the HTTP boundary by reading in chunks and
    # aborting early if the upload exceeds max_upload_size_mb.
    original_filename = Path(file.filename or "upload").name
    safe_stem = uuid.uuid4().hex
    suffix = Path(original_filename).suffix.lower() or ".xlsx"
    dest_path = uploads_dir / f"{safe_stem}{suffix}"
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    try:
        total_written = 0
        with open(dest_path, "wb") as out:
            while True:
                chunk = file.file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_bytes:
                    logger.warning(
                        "Upload '%s' rejected: exceeds %d MB limit",
                        original_filename,
                        settings.max_upload_size_mb,
                    )
                    # Remove the partially-written file before returning.
                    dest_path.unlink(missing_ok=True)
                    return _upload_error_response(
                        request,
                        db,
                        f"File exceeds the {settings.max_upload_size_mb} MB size limit.",
                    )
                out.write(chunk)
    except Exception as exc:
        logger.error("Failed to save uploaded file: %s", exc)
        dest_path.unlink(missing_ok=True)
        return _upload_error_response(request, db, "Failed to save the uploaded file.")

    ingest_succeeded = False
    try:
        upload, stats = ingest_file(db, dest_path, original_filename)
        ingest_succeeded = True
        logger.info(
            "Import succeeded: %d records from '%s'",
            stats.total_records,
            original_filename,
        )
        return RedirectResponse(url="/dashboard", status_code=303)

    except DuplicateFileError as exc:
        logger.info("Duplicate upload rejected: %s", exc)
        return _upload_warning_response(request, db, str(exc))

    except IngestError as exc:
        logger.warning("Ingest error for '%s': %s", original_filename, exc)
        return _upload_error_response(request, db, str(exc))

    except Exception as exc:
        logger.exception("Unexpected error during ingestion of '%s'", original_filename)
        return _upload_error_response(request, db, f"Unexpected error: {exc}")

    finally:
        # Remove the saved file on any failure path. On success the file
        # stays in uploads_dir for provenance. On DuplicateFileError and
        # all other error paths, the file is not referenced anywhere and
        # must be cleaned up to avoid unbounded disk accumulation.
        if not ingest_succeeded and dest_path.exists():
            try:
                dest_path.unlink()
            except OSError as exc:
                logger.warning("Could not remove orphaned upload file '%s': %s", dest_path, exc)


def _get_upload_history(db: Session) -> list[Upload]:
    return db.query(Upload).order_by(desc(Upload.upload_date)).limit(20).all()


def _upload_error_response(request: Request, db: Session, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "uploads": _get_upload_history(db),
            "flash": message,
            "flash_type": "error",
        },
        status_code=400,
    )


def _upload_warning_response(request: Request, db: Session, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "uploads": _get_upload_history(db),
            "flash": message,
            "flash_type": "warning",
        },
        status_code=409,
    )
