from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from server.repositories.configs import get_provider_config
from server.repositories.files import (
    create_file,
    delete_file,
    get_file,
    get_file_source,
    list_files,
    update_file_text,
)
from server.schemas.file import FileDetail, FileRecord, FilesResponse
from server.services.file_extract import FileExtractError, extract_text_async


router = APIRouter(prefix="/api/files", tags=["files"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.get("", response_model=FilesResponse)
def get_files() -> FilesResponse:
    return FilesResponse(files=list_files())


@router.post("", response_model=FileRecord)
async def upload_file(file: UploadFile = File(...)) -> FileRecord:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 20MB 限制")

    filename = file.filename or "untitled"
    try:
        text_content = await extract_text_async(
            filename, raw, file.content_type, get_provider_config()
        )
    except FileExtractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return create_file(
        filename=filename,
        raw=raw,
        mime_type=file.content_type,
        text_content=text_content,
    )


@router.post("/{file_id}/reextract", response_model=FileRecord)
async def reextract_file(file_id: str) -> FileRecord:
    """Re-run extraction on an already stored file (e.g. after enabling OCR).

    Note: re-index the knowledge base afterwards so chunks pick up the new text.
    """
    source = get_file_source(file_id)
    if not source:
        raise HTTPException(status_code=404, detail="File not found")

    stored_path, filename, mime_type = source
    try:
        raw = Path(stored_path).read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=410, detail="原始文件已丢失，请重新上传") from exc

    try:
        text_content = await extract_text_async(
            filename, raw, mime_type, get_provider_config()
        )
    except FileExtractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = update_file_text(file_id, text_content)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    return record


@router.get("/{file_id}", response_model=FileDetail)
def get_file_by_id(file_id: str) -> FileDetail:
    detail = get_file(file_id)
    if not detail:
        raise HTTPException(status_code=404, detail="File not found")
    return detail


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_file(file_id: str) -> Response:
    delete_file(file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
