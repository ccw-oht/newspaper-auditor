"""Pydantic schemas for API responses and requests."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuditOut(BaseModel):
    id: int
    paper_id: int
    timestamp: datetime
    has_pdf: Optional[str] = None
    pdf_only: Optional[str] = None
    paywall: Optional[str] = None
    notices: Optional[str] = None
    responsive: Optional[str] = None
    sources: Optional[str] = None
    notes: Optional[str] = None
    homepage_html: Optional[str] = None

    class Config:
        orm_mode = True


class PaperOut(BaseModel):
    id: int
    state: Optional[str] = None
    city: Optional[str] = None
    paper_name: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    audits: List[AuditOut] = Field(default_factory=list)

    class Config:
        orm_mode = True


class AuditBatchRequest(BaseModel):
    ids: List[int] = Field(..., description="Paper IDs to audit")


class AuditSummary(BaseModel):
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    has_pdf: Optional[str] = None
    pdf_only: Optional[str] = None
    paywall: Optional[str] = None
    notices: Optional[str] = None
    responsive: Optional[str] = None
    sources: Optional[str] = None
    notes: Optional[str] = None
    homepage_preview: Optional[str] = None


class PaperSummary(BaseModel):
    id: int
    state: Optional[str] = None
    city: Optional[str] = None
    paper_name: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    latest_audit: Optional[AuditSummary] = None


class PaperListResponse(BaseModel):
    total: int
    items: List[PaperSummary]


class PaperDetail(BaseModel):
    id: int
    state: Optional[str] = None
    city: Optional[str] = None
    paper_name: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    latest_audit: Optional[AuditSummary] = None
    audits: List[AuditOut] = Field(default_factory=list)


class PaperUpdate(BaseModel):
    state: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    paper_name: Optional[str] = Field(default=None)
    website_url: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    mailing_address: Optional[str] = Field(default=None)
    county: Optional[str] = Field(default=None)
    extra_data: Optional[Dict[str, Any]] = Field(default=None)
