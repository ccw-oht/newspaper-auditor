from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base

class Paper(Base):
    __tablename__ = "papers"
    id = Column(Integer, primary_key=True, index=True)
    state = Column(String)
    city = Column(String, nullable=False)
    paper_name = Column(String, nullable=False)
    website_url = Column(String, index=True)
    phone = Column(String)
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
