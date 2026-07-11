from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from server.repositories.configs import get_provider_config
from server.repositories.knowledge import (
    bind_file,
    create_knowledge,
    delete_knowledge,
    get_knowledge,
    knowledge_exists,
    list_knowledge,
    unbind_file,
    update_knowledge,
)
from server.schemas.knowledge import (
    BindFileRequest,
    IndexResult,
    Knowledge,
    KnowledgeCreate,
    KnowledgeDetail,
    KnowledgeListResponse,
    KnowledgeUpdate,
    RetrievalChunk,
    RetrievalQuery,
    RetrievalResult,
)
from server.services.rag import index_knowledge, query_knowledge

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("", response_model=KnowledgeListResponse)
def get_knowledge_list() -> KnowledgeListResponse:
    return KnowledgeListResponse(knowledge=list_knowledge())


@router.post("", response_model=Knowledge)
def post_knowledge(payload: KnowledgeCreate) -> Knowledge:
    return create_knowledge(payload.name, payload.description)


@router.get("/{knowledge_id}", response_model=KnowledgeDetail)
def get_knowledge_detail(knowledge_id: str) -> KnowledgeDetail:
    detail = get_knowledge(knowledge_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return detail


@router.put("/{knowledge_id}", response_model=Knowledge)
def put_knowledge(knowledge_id: str, payload: KnowledgeUpdate) -> Knowledge:
    updated = update_knowledge(knowledge_id, payload.name, payload.description)
    if not updated:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return updated


@router.delete("/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_knowledge(knowledge_id: str) -> Response:
    delete_knowledge(knowledge_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{knowledge_id}/files", response_model=KnowledgeDetail)
def bind_knowledge_file(knowledge_id: str, payload: BindFileRequest) -> KnowledgeDetail:
    ok = bind_file(knowledge_id, payload.file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Knowledge base or file not found")
    detail = get_knowledge(knowledge_id)
    assert detail is not None
    return detail


@router.delete("/{knowledge_id}/files/{file_id}", response_model=KnowledgeDetail)
def unbind_knowledge_file(knowledge_id: str, file_id: str) -> KnowledgeDetail:
    if not knowledge_exists(knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    unbind_file(knowledge_id, file_id)
    detail = get_knowledge(knowledge_id)
    assert detail is not None
    return detail


@router.post("/{knowledge_id}/index", response_model=IndexResult)
async def index_knowledge_base(knowledge_id: str) -> IndexResult:
    if not knowledge_exists(knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    config = get_provider_config()
    result = await index_knowledge(config, config.embedding_model, knowledge_id)
    return IndexResult(embedding_model=config.embedding_model, **result)


@router.post("/{knowledge_id}/query", response_model=RetrievalResult)
async def query_knowledge_base(knowledge_id: str, payload: RetrievalQuery) -> RetrievalResult:
    if not knowledge_exists(knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    config = get_provider_config()
    chunks = await query_knowledge(
        config,
        config.embedding_model,
        knowledge_id,
        payload.query,
        payload.top_k,
        mode=payload.mode,
        rerank=payload.rerank,
    )
    return RetrievalResult(chunks=[RetrievalChunk(**chunk) for chunk in chunks])
