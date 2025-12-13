"""Repository layer for knowledge base operations (Supabase/Postgres-backed)."""

from typing import List, Dict, Any, Optional
import uuid
from pathlib import Path

import numpy as np


from coachai.clients.supabase_client import SupabaseClient
from coachai.clients.postgres_client import PostgresClient
from coachai.clients.cohere_client import CohereClient
from coachai.core.config import Config


class KnowledgeRepository:
    def __init__(self, embed_model_name: str = "all-MiniLM-L6-v2"):
        self._supabase_user: Optional[SupabaseClient] = None
        self._supabase_service: Optional[SupabaseClient] = None
        self._pg: Optional[PostgresClient] = None
        self._user_id: Optional[str] = None

        try:
            self._cohere = CohereClient()
        except Exception:
            self._cohere = None

        self.embed_model_name = embed_model_name
        self.lessons: List[Dict[str, Any]] = []

        try:
            Path('logs').mkdir(exist_ok=True)
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        try:
            with open('logs/knowledge_repository.log', 'a', encoding='utf-8') as lf:
                lf.write('---\n')
                lf.write(msg + '\n')
        except Exception:
            pass

    def set_user_context(self, user_id: Optional[str], access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> None:
        """Configure repository to operate under a signed-in user (RLS)."""
        self._user_id = str(user_id) if user_id else None
        # Use anon key + user JWT for RLS-protected reads/writes.
        if access_token:
            self._supabase_user = SupabaseClient(access_token=access_token, refresh_token=refresh_token)
        else:
            self._supabase_user = None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self._cohere or not self._cohere.is_available():
            raise RuntimeError('Cohere embeddings not available. Ensure `cohere` is installed and COHERE_API_KEY is set.')
        return self._cohere.embed(texts)

    def _get_supabase(self) -> Optional[SupabaseClient]:
        # Prefer user-scoped client if available.
        if self._supabase_user is not None:
            return self._supabase_user
        try:
            # anon client without JWT (read-only if RLS requires auth)
            return SupabaseClient()
        except Exception:
            return None

    def _get_supabase_service(self) -> Optional[SupabaseClient]:
        if self._supabase_service is None:
            try:
                self._supabase_service = SupabaseClient(use_service_role=True)
            except Exception:
                self._supabase_service = None
        return self._supabase_service

    def _user_bucket(self, owner_id: str) -> str:
        # Per-user bucket naming. Supabase bucket names should be lowercase.
        return f"user-{str(owner_id).lower()}"

    def _get_postgres(self) -> Optional[PostgresClient]:
        if self._pg is None:
            try:
                self._pg = PostgresClient()
            except Exception:
                self._pg = None
        return self._pg

    def load(self) -> bool:
        sup = self._get_supabase()
        if not sup:
            self.lessons = []
            return True

        try:
            res = sup.table_select('lessons', limit=5000)
            self.lessons = res.data if res and getattr(res, 'data', None) else []
            return True
        except Exception:
            self.lessons = []
            return False

    def all(self) -> List[Dict[str, Any]]:
        return self.lessons

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        pg = self._get_postgres()
        if pg:
            rows: List[Dict[str, Any]] = []
            try:
                emb = self.embed_texts([query])[0]
                rows = pg.vector_search(emb, source_table='lessons', top_k=top_k)
            except Exception:
                self._log('search: pgvector path failed (embed/vector_search threw)')
                rows = []

            if not rows:
                # Fallback to in-memory similarity if vector search returns no rows.
                self._log('search: pgvector returned 0 rows, falling back to in-memory similarity')
                pg = None

            sup = self._get_supabase()
            results = []
            for r in rows:
                sid = r.get('source_id')
                lesson = None
                if sup:
                    try:
                        res = sup.table_select('lessons', {'id': sid}, returning='*')
                        if res and getattr(res, 'data', None):
                            lesson = res.data[0]
                    except Exception:
                        lesson = None

                if not lesson:
                    lesson = next((l for l in self.lessons if l.get('id') == sid or str(l.get('id')) == str(sid)), None)

                if lesson:
                    lesson_copy = dict(lesson)
                    dist = r.get('distance')
                    lesson_copy['distance'] = dist
                    try:
                        # Convert cosine distance (lower is better) to similarity (higher is better)
                        lesson_copy['similarity'] = 1.0 / (1.0 + float(dist))
                    except Exception:
                        lesson_copy['similarity'] = None
                    results.append(lesson_copy)

            return results

        if not self.lessons:
            self.load()

        texts = [f"{l.get('topic', '')}: {l.get('content', '')}" for l in self.lessons]
        if not texts:
            return []

        try:
            embeddings = self.embed_texts(texts)
            query_emb = self.embed_texts([query])[0]
        except Exception:
            return []

        embeddings_np = np.array(embeddings, dtype=float)
        query_np = np.array(query_emb, dtype=float)

        sims = (embeddings_np @ query_np.T).squeeze() / ((np.linalg.norm(embeddings_np, axis=1) * np.linalg.norm(query_np)) + 1e-10)
        ranked_idx = list(np.argsort(sims)[-min(top_k, len(sims)):][::-1])

        results = []
        for idx in ranked_idx:
            lesson_copy = dict(self.lessons[idx])
            lesson_copy['similarity'] = float(sims[idx])
            results.append(lesson_copy)
        return results

    def add(self, topic: str, content: str, subject: str, level: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        sup = self._get_supabase()
        rec = {
            'owner_id': owner_id,
            'title': topic,
            'topic': topic,
            'subject': subject,
            'level': level,
            'content': content,
            'visibility': 'private'
        }

        if not sup:
            new_rec = dict(rec)
            new_rec['id'] = str(uuid.uuid4())
            self.lessons.append(new_rec)
            return new_rec

        try:
            res = sup.table_insert('lessons', rec)
            err = getattr(res, 'error', None)
            if err:
                return None

            if res and getattr(res, 'data', None):
                new_id = res.data[0].get('id')
                self.load()

                # Cohere-only embeddings: if embedding fails, treat as failure so RAG stays correct.
                try:
                    emb = self.embed_texts([content])[0]
                    metadata = {'topic': topic, 'subject': subject, 'owner_id': owner_id}
                    if new_id:
                        eid = self.add_embedding_for_lesson(new_id, emb, metadata)
                        if not eid:
                            self._log(f'add: embedding insert returned empty id for lesson_id={new_id}')
                            # Best-effort cleanup so we don't keep non-retrievable lessons.
                            try:
                                svc = self._get_supabase_service()
                                if svc:
                                    svc.table_delete('lessons', 'id', new_id)
                            except Exception as e:
                                self._log(f'add: cleanup delete failed: {repr(e)} lesson_id={new_id}')
                            return None
                except Exception:
                    self._log(f'add: embedding failed for lesson_id={new_id} (check COHERE_API_KEY/COHERE_MODEL/SUPABASE_DB_URL)')
                    try:
                        svc = self._get_supabase_service()
                        if svc and new_id:
                            svc.table_delete('lessons', 'id', new_id)
                    except Exception as e:
                        self._log(f'add: cleanup delete failed: {repr(e)} lesson_id={new_id}')
                    return None

                return res.data[0]
        except Exception:
            return None

        return None

    def upsert_lesson_to_supabase(self, lesson: Dict[str, Any], owner_id: Optional[str] = None) -> Optional[str]:
        sup = self._get_supabase()
        if not sup:
            return None

        rec = {
            'owner_id': owner_id,
            'title': lesson.get('topic'),
            'topic': lesson.get('topic'),
            'subject': lesson.get('subject'),
            'level': lesson.get('level'),
            'content': lesson.get('content'),
            'visibility': lesson.get('visibility', 'private')
        }
        res = sup.table_insert('lessons', rec)
        if res and getattr(res, 'data', None):
            self.load()
            return res.data[0].get('id')
        return None

    def add_embedding_for_lesson(self, lesson_id: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        pg = self._get_postgres()
        if not pg:
            return None
        return pg.insert_embedding('lessons', lesson_id, embedding, metadata)

    def add_embedding_for_source(self, source_table: str, source_id: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        pg = self._get_postgres()
        if not pg:
            return None
        return pg.insert_embedding(source_table, source_id, embedding, metadata)

    def upload_attachment(self, owner_id: str, bucket: str, path: str, file_bytes: bytes, content_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # Enforce per-user buckets.
        bucket = self._user_bucket(owner_id)

        # Generate a stable object name when not provided.
        if not path:
            ext = 'bin'
            ct = (content_type or '').lower()
            if 'png' in ct:
                ext = 'png'
            elif 'jpeg' in ct or 'jpg' in ct:
                ext = 'jpg'
            elif 'webp' in ct:
                ext = 'webp'
            path = f"attachments/{uuid.uuid4().hex}.{ext}"

        # Ensure bucket exists and upload via service role (storage policies often block user JWT uploads).
        svc = self._get_supabase_service()
        if not svc:
            self._log('upload_attachment: service client not available (missing SUPABASE_SERVICE_ROLE_KEY?)')
            return None
        try:
            svc.storage_create_bucket(bucket, public=False)
        except Exception as e:
            # Ignore if it already exists.
            self._log(f'upload_attachment: create_bucket warning: {repr(e)}')

        sup = self._get_supabase()
        if not sup:
            self._log('upload_attachment: user client not available')
            return None
        try:
            svc.storage_upload(bucket, path, file_bytes, content_type=content_type)

            # Buckets are private: store a signed URL (short-lived) for immediate usage.
            signed = ''
            try:
                signed_res = svc.storage_create_signed_url(bucket, path, expires_in=3600)
                if isinstance(signed_res, dict):
                    signed = signed_res.get('signedURL') or signed_res.get('signedUrl') or signed_res.get('signed_url') or ''
                else:
                    signed = getattr(signed_res, 'signedURL', None) or getattr(signed_res, 'signedUrl', None) or ''
            except Exception as e:
                self._log(f'upload_attachment: create_signed_url failed: {repr(e)}')

            rec = {'owner_id': owner_id, 'bucket': bucket, 'path': path, 'public_url': signed}
            res = sup.table_insert('attachments', rec)
            return res.data[0] if getattr(res, 'data', None) else None
        except Exception as e:
            self._log(f'upload_attachment failed: {repr(e)} bucket={bucket} path={path}')
            return None

    def delete_lesson(self, lesson_id: str) -> bool:
        sup = self._get_supabase()
        pg = self._get_postgres()

        def _attempt_delete(sup_client) -> bool:
            try:
                res = sup_client.table_delete('lessons', 'id', lesson_id)
                err = getattr(res, 'error', None)
                if err:
                    return False
                try:
                    self.load()
                except Exception:
                    pass
                return True
            except Exception:
                return False

        if sup:
            ok = _attempt_delete(sup)
            if not ok and Config.SUPABASE_SERVICE_ROLE_KEY:
                try:
                    svc = SupabaseClient(key=Config.SUPABASE_SERVICE_ROLE_KEY)
                    ok = _attempt_delete(svc)
                except Exception:
                    ok = False
            if not ok:
                return False
        else:
            self.lessons = [l for l in self.lessons if str(l.get('id')) != str(lesson_id)]

        if pg:
            try:
                pg.delete_embeddings_for_source('lessons', lesson_id)
            except Exception:
                pass

        return True
