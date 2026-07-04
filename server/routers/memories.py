from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.repositories.memories import create_memory, delete_memory, list_memories, update_memory
from server.schemas.memory import MemoriesResponse, Memory, MemoryCreate, MemoryUpdate


router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("", response_model=MemoriesResponse)
def get_memories() -> MemoriesResponse:
    return MemoriesResponse(memories=list_memories())


@router.post("", response_model=Memory)
def post_memory(payload: MemoryCreate) -> Memory:
    return create_memory(payload)


@router.put("/{memory_id}", response_model=Memory)
def put_memory(memory_id: str, payload: MemoryUpdate) -> Memory:
    memory = update_memory(memory_id, payload)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.delete("/{memory_id}")
def delete_memory_by_id(memory_id: str) -> dict[str, bool]:
    ok = delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}
