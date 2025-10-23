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
    chain_owner: Optional[str] = None
    cms_platform: Optional[str] = None
    cms_vendor: Optional[str] = None

    class Config:
        from_attributes = True


class PaperOut(BaseModel):
    id: int
    state: Optional[str] = None
    city: Optional[str] = None
    paper_name: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    chain_owner: Optional[str] = None
    cms_platform: Optional[str] = None
    cms_vendor: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    audits: List[AuditOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


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
    chain_owner: Optional[str] = None
    cms_platform: Optional[str] = None
    cms_vendor: Optional[str] = None


class PaperSummary(BaseModel):
    id: int
    state: Optional[str] = None
    city: Optional[str] = None
    paper_name: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    chain_owner: Optional[str] = None
    cms_platform: Optional[str] = None
    cms_vendor: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    latest_audit: Optional[AuditSummary] = None


class PaperListOptions(BaseModel):
    states: List[str] = Field(default_factory=list)
    cities: List[str] = Field(default_factory=list)
    chainOwners: List[str] = Field(default_factory=list)
    cmsPlatforms: List[str] = Field(default_factory=list)
    cmsVendors: List[str] = Field(default_factory=list)


class PaperListResponse(BaseModel):
    total: int
    items: List[PaperSummary]
    options: PaperListOptions


class PaperIdList(BaseModel):
    total: int
    ids: List[int]


class PaperDetail(BaseModel):
    id: int
    state: Optional[str] = None
    city: Optional[str] = None
    paper_name: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    chain_owner: Optional[str] = None
    cms_platform: Optional[str] = None
    cms_vendor: Optional[str] = None
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
    chain_owner: Optional[str] = Field(default=None)
    cms_platform: Optional[str] = Field(default=None)
    cms_vendor: Optional[str] = Field(default=None)
    extra_data: Optional[Dict[str, Any]] = Field(default=None)


class ImportPreviewRow(BaseModel):
    temp_id: str
    status: str
    allowed_actions: List[str]
    data: Dict[str, Any]
    existing: Optional[Dict[str, Any]] = None
    differences: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)


class ImportPreviewSummary(BaseModel):
    new: int = 0
    update: int = 0
    duplicate: int = 0
    invalid: int = 0


class ImportPreviewResponse(BaseModel):
    rows: List[ImportPreviewRow]
    summary: ImportPreviewSummary


class ImportCommitRow(BaseModel):
    temp_id: str
    action: str
    data: Dict[str, Any]
    existing_id: Optional[int] = None
    status: Optional[str] = None


class ImportCommitRequest(BaseModel):
    rows: List[ImportCommitRow]


class ImportCommitResult(BaseModel):
    inserted: int
    updated: int
    skipped: int


class ExportRequest(BaseModel):
    ids: List[int]
