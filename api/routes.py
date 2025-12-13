"""
API routes for Knowledge Base management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .models import KnowledgeEntry, get_db
from .schemas import (
    KnowledgeEntry as KnowledgeEntrySchema,
    KnowledgeEntryCreate,
    KnowledgeEntryUpdate,
    SearchQuery,
    SearchResult
)

router = APIRouter()

# Initialize the sentence transformer model
embed_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')

@router.post("/entries/", response_model=KnowledgeEntrySchema)
def create_entry(entry: KnowledgeEntryCreate, db: Session = Depends(get_db)):
    """Create a new knowledge entry"""
    db_entry = KnowledgeEntry(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

@router.get("/entries/", response_model=List[KnowledgeEntrySchema])
def read_entries(
    skip: int = 0,
    limit: int = 100,
    subject: Optional[str] = None,
    level: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all knowledge entries with optional filtering"""
    query = db.query(KnowledgeEntry)

    if subject:
        query = query.filter(KnowledgeEntry.subject.ilike(f"%{subject}%"))
    if level:
        query = query.filter(KnowledgeEntry.level.ilike(f"%{level}%"))

    entries = query.offset(skip).limit(limit).all()
    return entries

@router.get("/entries/{entry_id}", response_model=KnowledgeEntrySchema)
def read_entry(entry_id: int, db: Session = Depends(get_db)):
    """Get a specific knowledge entry by ID"""
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry

@router.put("/entries/{entry_id}", response_model=KnowledgeEntrySchema)
def update_entry(entry_id: int, entry_update: KnowledgeEntryUpdate, db: Session = Depends(get_db)):
    """Update a knowledge entry"""
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    for field, value in entry_update.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    """Delete a knowledge entry"""
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    db.delete(entry)
    db.commit()
    return {"message": "Entry deleted successfully"}

@router.post("/search/", response_model=List[SearchResult])
def search_entries(search_query: SearchQuery, db: Session = Depends(get_db)):
    """Search knowledge entries using semantic similarity"""
    # Get all entries, optionally filtered
    query = db.query(KnowledgeEntry)

    if search_query.subject_filter:
        query = query.filter(KnowledgeEntry.subject.ilike(f"%{search_query.subject_filter}%"))
    if search_query.level_filter:
        query = query.filter(KnowledgeEntry.level.ilike(f"%{search_query.level_filter}%"))

    entries = query.all()

    if not entries:
        return []

    # Create texts for embedding
    texts = [f"{entry.topic}: {entry.content}" for entry in entries]

    # Generate embeddings
    query_embedding = embed_model.encode([search_query.query], convert_to_numpy=True)
    entry_embeddings = embed_model.encode(texts, convert_to_numpy=True)

    # Calculate similarities
    similarities = cosine_similarity(query_embedding, entry_embeddings)[0]

    # Create result pairs and sort by similarity
    results = []
    for entry, similarity in zip(entries, similarities):
        results.append(SearchResult(
            entry=KnowledgeEntrySchema.model_validate(entry),
            similarity=float(similarity)
        ))

    # Sort by similarity (descending) and return top_k
    results.sort(key=lambda x: x.similarity, reverse=True)
    return results[:search_query.top_k]

@router.get("/subjects/")
def get_subjects(db: Session = Depends(get_db)):
    """Get all available subjects"""
    subjects = db.query(KnowledgeEntry.subject).distinct().all()
    return {"subjects": [s[0] for s in subjects]}

@router.get("/levels/")
def get_levels(db: Session = Depends(get_db)):
    """Get all available levels"""
    levels = db.query(KnowledgeEntry.level).distinct().all()
    return {"levels": [l[0] for l in levels]}

@router.get("/stats/")
def get_stats(db: Session = Depends(get_db)):
    """Get database statistics"""
    total_entries = db.query(KnowledgeEntry).count()
    subjects_count = db.query(KnowledgeEntry.subject).distinct().count()
    levels_count = db.query(KnowledgeEntry.level).distinct().count()

    subject_breakdown = db.query(
        KnowledgeEntry.subject,
        KnowledgeEntry.level,
        db.func.count(KnowledgeEntry.id)
    ).group_by(KnowledgeEntry.subject, KnowledgeEntry.level).all()

    return {
        "total_entries": total_entries,
        "unique_subjects": subjects_count,
        "unique_levels": levels_count,
        "breakdown": [
            {"subject": s, "level": l, "count": c}
            for s, l, c in subject_breakdown
        ]
    }
