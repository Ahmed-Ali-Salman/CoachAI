"""Protected server-side endpoints that use the SERVICE_ROLE key.

These endpoints are intended to be called from trusted backends (not public
browser clients) because they perform privileged operations such as writing
embeddings to Postgres and uploading to Supabase Storage using the service role.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from typing import Optional

from coachai.schemas.schemas import ProtectedLesson, EmbeddingIn, GeneratedQuestionIn, AnswerIn

from coachai.repositories.knowledge_repository import KnowledgeRepository
from coachai.client.supabase_client import SupabaseClient
from coachai.client.postgres_client import PostgresClient
from coachai.core.config import Config

router = APIRouter()


def require_service_key(x_service_key: Optional[str] = Header(None)):
    """Simple header-based check to ensure caller knows the service key.

    This is a lightweight guard. In production you should use mTLS, internal
    network, or a signed JWT instead.
    """
    if not x_service_key or x_service_key != Config.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: invalid service key")
    return True


@router.post("/lessons/")
def create_lesson(lesson: ProtectedLesson, authorized: bool = Depends(require_service_key)):
    repo = KnowledgeRepository()
    # Upsert to Supabase
    lesson_id = repo.upsert_lesson_to_supabase(lesson.model_dump(), owner_id=lesson.owner_id)
    # Compute embedding using the local embedder if available
    try:
        emb = repo.embed_texts([lesson.content])[0]
        if lesson_id:
            repo.add_embedding_for_lesson(lesson_id, emb, {'source': 'lessons', 'topic': lesson.topic})
    except Exception:
        pass
    return {"id": lesson_id}


@router.post("/embeddings/")
def insert_embedding(payload: EmbeddingIn, authorized: bool = Depends(require_service_key)):
    pg = PostgresClient()
    eid = pg.insert_embedding(payload.source_table, payload.source_id, payload.embedding, payload.metadata)
    return {"id": eid}


@router.post("/attachments/")
async def upload_attachment(owner_id: str, bucket: Optional[str] = None, path: Optional[str] = None, file: UploadFile = File(...), authorized: bool = Depends(require_service_key)):
    sup = SupabaseClient()
    bucket = bucket or Config.SUPABASE_STORAGE_BUCKET
    # If no path provided, generate one
    import uuid
    path = path or f"attachments/{owner_id}/{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()
    sup.storage_upload(bucket, path, content, content_type=file.content_type)
    public = sup.storage_get_public_url(bucket, path)
    rec = {'owner_id': owner_id, 'bucket': bucket, 'path': path, 'public_url': public}
    res = sup.table_insert('attachments', rec)
    return {'attachment': res.data[0] if getattr(res, 'data', None) else None}


@router.post("/generated_questions/")
def store_generated_question(q: GeneratedQuestionIn, authorized: bool = Depends(require_service_key)):
    sup = SupabaseClient()
    rec = q.model_dump()
    res = sup.table_insert('generated_questions', rec)
    return {'result': res.data[0] if getattr(res, 'data', None) else None}


@router.post("/answers/")
def store_answer(a: AnswerIn, authorized: bool = Depends(require_service_key)):
    sup = SupabaseClient()
    rec = a.model_dump()
    res = sup.table_insert('answers', rec)
    return {'result': res.data[0] if getattr(res, 'data', None) else None}
