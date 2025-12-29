from datetime import datetime

from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base

class Paper(Base):
    __tablename__ = "papers"
    id = Column(Integer, primary_key=True, index=True)
    state = Column(String)
    city = Column(String, nullable=False)
    paper_name = Column(String, nullable=False)
    website_url = Column(String, index=True)
    phone = Column(String)
    email = Column(String)
    mailing_address = Column(String)
    county = Column(String)
    chain_owner = Column(String)
    cms_platform = Column(String)
    cms_vendor = Column(String)
    extra_data = Column(JSON, default=dict)
    audit_overrides = Column(JSON, default=dict)

    audits = relationship("Audit", back_populates="paper")

class Audit(Base):
    __tablename__ = "audits"
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)

    has_pdf = Column(String)
    pdf_only = Column(String)
    paywall = Column(String)
    notices = Column(String)
    responsive = Column(String)
    sources = Column(String)
    notes = Column(String)
    homepage_html = Column(Text)
    chain_owner = Column(String)
    cms_platform = Column(String)
    cms_vendor = Column(String)

    paper = relationship("Paper", back_populates="audits")


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    filter_params = Column(JSON, default=dict)
    query_string = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    papers = relationship("ResearchSessionPaper", back_populates="session", cascade="all, delete-orphan")
    features = relationship("ResearchFeature", back_populates="session", cascade="all, delete-orphan")


class ResearchSessionPaper(Base):
    __tablename__ = "research_session_papers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id", ondelete="CASCADE"))
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="SET NULL"), nullable=True)
    snapshot = Column(JSON, default=dict)

    session = relationship("ResearchSession", back_populates="papers")
    paper = relationship("Paper")


class ResearchFeature(Base):
    __tablename__ = "research_features"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    keywords = Column(ARRAY(String), nullable=False)
    desired_examples = Column(Integer, default=5)
    status = Column(String, default="pending")
    last_evaluated_at = Column(DateTime)
    evidence = Column(JSON, default=dict)
    error = Column(Text)

    session = relationship("ResearchSession", back_populates="features")
