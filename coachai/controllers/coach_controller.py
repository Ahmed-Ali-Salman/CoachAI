"""Controller layer for CoachAI.

Controllers adapt transport-layer inputs to service calls.
"""

from typing import Optional, List, Dict, Any

from coachai.services.coach_service import CoachService


class CoachController:
    def __init__(self, service: Optional[CoachService] = None):
        self.service = service or CoachService()

    def signup(self, email: str, password: str) -> Dict[str, Any]:
        sup = self.service.knowledge_repo._get_supabase()
        if not sup:
            raise RuntimeError('Supabase not configured')
        return sup.auth_sign_up(email, password)

    def signin(self, email: str, password: str) -> Dict[str, Any]:
        sup = self.service.knowledge_repo._get_supabase()
        if not sup:
            raise RuntimeError('Supabase not configured')
        return sup.auth_sign_in(email, password)

    def submit_query(self, user_id: str, text_query: str, images: Optional[List[bytes]] = None, content_types: Optional[List[str]] = None) -> Optional[str]:
        return self.service.store_user_query(user_id, text_query, image_bytes_list=images, content_types=content_types)

    def generate_question(self, lesson_id: Optional[str], query_id: Optional[str], question_text: str, model: str = '') -> Optional[str]:
        return self.service.store_generated_question(lesson_id, query_id, question_text, author_model=model)

    def evaluate(self, question: str, student_answer: str, correct_concept: str) -> str:
        return self.service.evaluate_answer(question, student_answer, correct_concept)
