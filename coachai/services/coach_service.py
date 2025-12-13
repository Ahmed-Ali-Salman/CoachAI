"""Service layer for CoachAI."""

from typing import List, Dict, Any, Optional
import uuid

from coachai.core.config import Config
from coachai.repositories.knowledge_repository import KnowledgeRepository
from coachai.services.model_handler import ModelHandler


class CoachService:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.knowledge_repo = KnowledgeRepository(self.config.EMBED_MODEL_NAME)
        self.model_handler = ModelHandler(self.config)
        self.current_user_id: Optional[str] = None

    def set_user_context(self, user_id: Optional[str], access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> None:
        self.current_user_id = str(user_id) if user_id else None
        self.knowledge_repo.set_user_context(self.current_user_id, access_token=access_token, refresh_token=refresh_token)

    def initialize(self) -> bool:
        try:
            self.knowledge_repo.load()
        except Exception:
            pass
        return bool(self.model_handler.load_model())

    def find_relevant(self, query: str, top_k: Optional[int] = None):
        return self.knowledge_repo.search(query, top_k=top_k or self.config.TOP_K)

    def generate_explanation(self, query: str, relevant: List[Dict[str, Any]], image=None):
        if not relevant:
            try:
                relevant = self.find_relevant(query, top_k=self.config.TOP_K)
            except Exception:
                relevant = []

        if relevant:
            retrieved_lines = []
            for l in relevant:
                lid = l.get('id')
                topic = l.get('topic', '')
                content_text = l.get('content', '')
                sim = l.get('similarity', None)
                sim_str = f"{float(sim):.4f}" if sim is not None else "N/A"
                retrieved_lines.append(f"ID: {lid}\nTopic: {topic}\nSimilarity: {sim_str}\n{content_text}\n---")
            retrieved_section = "Retrieved documents:\n" + "\n".join(retrieved_lines)
        else:
            retrieved_section = "Retrieved documents: none available."

        system_prompt = "You are an expert learning coach with advanced visual analysis capabilities. Use the retrieved documents to ground answers and cite document IDs when relevant."
        user_prompt = f"{retrieved_section}\n\nQuestion: {query}\n\nProvide a clear, educational explanation that directly uses the retrieved documents."

        content = []
        if image is not None:
            content.append({
                'type': 'image',
                'image': image,
                'min_pixels': self.config.MIN_PIXELS,
                'max_pixels': self.config.MAX_PIXELS,
            })

        content.append({'type': 'text', 'text': user_prompt})

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': content}
        ]

        return self.model_handler.generate(messages)

    def generate_practice_question(self, topic: str):
        try:
            relevant = self.find_relevant(topic, top_k=self.config.TOP_K)
        except Exception:
            relevant = []

        if relevant:
            snippets = "\n".join([f"- {r.get('topic','')}: {r.get('content','')[:200]}" for r in relevant])
            prompt = f"Using the following materials:\n{snippets}\n\nCreate one practice question about {topic}. Make it challenging but appropriate. Provide only the question."
        else:
            prompt = f"Create one practice question about {topic}. Make it challenging but appropriate. Provide only the question."

        messages = [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}]
        q = self.model_handler.generate(messages, max_new_tokens=256, temperature=0.8)

        # Persist generated question (best-effort) when authenticated.
        try:
            if self.current_user_id:
                # Try to resolve lesson_id from cached lessons
                lesson_id = None
                for l in self.knowledge_repo.all():
                    if str(l.get('topic', '')).strip().lower() == str(topic).strip().lower():
                        lesson_id = l.get('id')
                        break
                self.store_generated_question(lesson_id=lesson_id, query_id=None, question_text=q, author_model=getattr(self.config, 'MODEL_NAME', ''))
        except Exception:
            pass

        return q

    def evaluate_answer(self, question: str, student_answer: str, correct_concept: str):
        try:
            relevant = self.find_relevant(question or correct_concept, top_k=self.config.TOP_K)
        except Exception:
            relevant = []

        if relevant:
            retrieved = "\n".join([f"ID:{r.get('id')} Topic:{r.get('topic')}\n{r.get('content','')[:300]}" for r in relevant])
            prompt = f"Retrieved documents:\n{retrieved}\n\nEvaluate this student answer in the context of the retrieved documents.\nQuestion: {question}\nAnswer: {student_answer}\nKey Concept: {correct_concept}\nProvide a score and brief feedback citing any documents used."
        else:
            prompt = f"Evaluate this student answer.\nQuestion: {question}\nAnswer: {student_answer}\nKey Concept: {correct_concept}\nProvide a score and brief feedback."

        messages = [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}]
        resp = self.model_handler.generate(messages, max_new_tokens=512)

        try:
            sup = self.knowledge_repo._get_supabase()
            if sup and self.current_user_id:
                rec = {
                    'question_id': None,
                    'user_id': self.current_user_id,
                    'user_answer': student_answer,
                    'model_answer': resp,
                    'grade': None,
                    'feedback': None
                }
                sup.table_insert('answers', rec)
        except Exception:
            pass

        return resp

    def store_user_query(self, user_id: str, text_query: str, image_bytes_list: Optional[list] = None, content_types: Optional[list] = None) -> Optional[str]:
        try:
            attachment_ids = []
            if image_bytes_list:
                for i, b in enumerate(image_bytes_list):
                    bucket = self.config.SUPABASE_STORAGE_BUCKET
                    # Per-user bucket is already unique; keep object names simple.
                    path = f"attachments/{uuid.uuid4().hex}_{i}.png"
                    att = self.knowledge_repo.upload_attachment(user_id, bucket, path, b, content_type=(content_types[i] if content_types and i < len(content_types) else 'image/png'))
                    if att and att.get('id'):
                        attachment_ids.append(att.get('id'))

            emb = self.knowledge_repo.embed_texts([text_query])[0]

            sup = self.knowledge_repo._get_supabase()
            qid = None
            if sup:
                rec = {'user_id': user_id, 'text_query': text_query, 'image_attachment_ids': attachment_ids}
                res = sup.table_insert('user_queries', rec)
                if res and getattr(res, 'data', None):
                    qid = res.data[0].get('id')

            # Backfill query_id + metadata on attachments now that query exists.
            if sup and qid and attachment_ids:
                for idx, aid in enumerate(attachment_ids):
                    try:
                        md = {
                            'source': 'user_query',
                            'query_id': str(qid),
                            'user_id': str(user_id),
                            'index': idx,
                            'content_type': (content_types[idx] if content_types and idx < len(content_types) else None),
                        }
                        sup.table_update('attachments', {'query_id': qid, 'metadata': md}, 'id', aid)
                    except Exception as e:
                        try:
                            self.knowledge_repo._log(f'store_user_query: failed to update attachment id={aid} query_id={qid}: {repr(e)}')
                        except Exception:
                            pass

            if qid:
                self.knowledge_repo.add_embedding_for_source('user_queries', qid, emb, {'source': 'user_query'})

            return qid
        except Exception:
            return None

    def store_generated_question(self, lesson_id: Optional[str], query_id: Optional[str], question_text: str, author_model: str = '') -> Optional[str]:
        sup = self.knowledge_repo._get_supabase()
        if not sup:
            return None
        rec = {'lesson_id': lesson_id, 'query_id': query_id, 'author_model': author_model, 'question_text': question_text}
        res = sup.table_insert('generated_questions', rec)
        if res and getattr(res, 'data', None):
            return res.data[0].get('id')
        return None
