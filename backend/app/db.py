import os
from datetime import datetime
from flask import current_app
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Enum, ARRAY, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import enum

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# Enums for data consistency
class DocumentStatus(enum.Enum):
    to_review = "to_review"
    safe = "safe"
    not_safe = "not_safe"
    accepted = "accepted"
    declined = "declined"


# Models
class Document(Base):
    """Each analyzed NDA or PDF."""
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_status", "status"),)

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    total_clauses = Column(Integer)
    compliance_score = Column(Float)
    compliance_details = Column(JSON)
    pdf_url = Column(String)
    report_url = Column(String)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.to_review)
    clauses = relationship("Clause", back_populates="document", cascade="all, delete-orphan")


class Clause(Base):
    """A clause extracted from a document."""
    __tablename__ = "clauses"
    __table_args__ = (Index("ix_clause_document_id", "document_id"),)

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    title = Column(String)
    body = Column(Text)
    pages = Column(ARRAY(Integer))  # e.g. [1,2]
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="clauses")
    prediction = relationship("Prediction", uselist=False, back_populates="clause", cascade="all, delete-orphan")
    rejections = relationship("Rejection", back_populates="clause", cascade="all, delete-orphan")


class Prediction(Base):
    """LLM-generated evaluation of a clause."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    clause_id = Column(Integer, ForeignKey("clauses.id", ondelete="CASCADE"))
    best_rule = Column(String)
    severity = Column(String)
    status = Column(String)
    reason = Column(Text)
    retrieved_rules = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    llm_evaluation = Column(JSON, nullable=True)
    clause = relationship("Clause", back_populates="prediction")


class Rejection(Base):
    """Manual correction of a clause evaluation."""
    __tablename__ = "rejections"

    id = Column(Integer, primary_key=True, index=True)
    clause_id = Column(Integer, ForeignKey("clauses.id", ondelete="CASCADE"))
    comment = Column(Text)
    new_status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    clause = relationship("Clause", back_populates="rejections")


# --- Initialization helper ---
def init_db():
    """Create tables if they don’t exist."""
    print("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    print("Database ready !")
