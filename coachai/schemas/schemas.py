"""
Pydantic schemas for API request/response models
"""

from pydantic import BaseModel
from typing import List, Optional

class KnowledgeEntryBase(BaseModel):
    topic: str
    content: str
    subject: str
    level: str

class KnowledgeEntryCreate(KnowledgeEntryBase):
    pass

class KnowledgeEntry(KnowledgeEntryBase):
    id: int

    class Config:
        from_attributes = True

class KnowledgeEntryUpdate(BaseModel):
    topic: Optional[str] = None
    content: Optional[str] = None
    subject: Optional[str] = None
    level: Optional[str] = None

class SearchQuery(BaseModel):
    query: str
    top_k: Optional[int] = 5
    subject_filter: Optional[str] = None
    level_filter: Optional[str] = None

class SearchResult(BaseModel):
    entry: KnowledgeEntry
    similarity: float


class ProtectedLesson(BaseModel):
    topic: str
    content: str
    subject: Optional[str] = None
    level: Optional[str] = None
    owner_id: Optional[str] = None


class EmbeddingIn(BaseModel):
    source_table: str
    source_id: str
    embedding: List[float]
    metadata: Optional[dict] = None


class GeneratedQuestionIn(BaseModel):
    lesson_id: Optional[str] = None
    query_id: Optional[str] = None
    author_model: Optional[str] = None
    question_text: str


class AnswerIn(BaseModel):
    question_id: Optional[str]
    user_id: str
    user_answer: str
    model_answer: Optional[str] = None
    grade: Optional[float] = None
    feedback: Optional[str] = None
