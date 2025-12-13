"""
Database models for Knowledge Base API
"""

from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class KnowledgeEntry(Base):
    """Knowledge base entry model"""
    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    subject = Column(String(100), nullable=False, index=True)
    level = Column(String(50), nullable=False, index=True)

    def __repr__(self):
        return f"<KnowledgeEntry(id={self.id}, topic='{self.topic}', subject='{self.subject}')>"

# Database configuration
DATABASE_URL = "sqlite:///./knowledge_base.db"  # For development, can be changed to PostgreSQL later

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Only for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
