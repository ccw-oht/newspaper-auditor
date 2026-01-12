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
    email: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    publication_frequency: Optional[str] = None
    chain_owner: Optional[str] = None
    cms_platform: Optional[str] = None
    cms_vendor: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    audit_overrides: Optional[Dict[str, Any]] = None
    audits: List[AuditOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class AuditBatchRequest(BaseModel):
    ids: List[int] = Field(..., description="Paper IDs to audit")


class LookupBatchRequest(BaseModel):
    ids: List[int] = Field(..., description="Paper IDs to lookup")


class LookupResult(BaseModel):
    paper_id: int
    updated: bool
    phone: Optional[str] = None
    email: Optional[str] = None
    mailing_address: Optional[str] = None
    lookup_metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


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
    overrides: Optional[Dict[str, Any]] = None


class PaperSummary(BaseModel):
    id: int
    state: Optional[str] = None
    city: Optional[str] = None
    paper_name: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    publication_frequency: Optional[str] = None
    chain_owner: Optional[str] = None
    cms_platform: Optional[str] = None
    cms_vendor: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    audit_overrides: Optional[Dict[str, Any]] = None
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
    email: Optional[str] = None
    mailing_address: Optional[str] = None
    county: Optional[str] = None
    publication_frequency: Optional[str] = None
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
    email: Optional[str] = Field(default=None)
    mailing_address: Optional[str] = Field(default=None)
    county: Optional[str] = Field(default=None)
    publication_frequency: Optional[str] = Field(default=None)
    chain_owner: Optional[str] = Field(default=None)
    cms_platform: Optional[str] = Field(default=None)
    cms_vendor: Optional[str] = Field(default=None)
    extra_data: Optional[Dict[str, Any]] = Field(default=None)
    audit_overrides: Optional[Dict[str, Any]] = Field(default=None)


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
    possible_duplicate: int = 0
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
    field_actions: Optional[Dict[str, str]] = None


class ImportCommitRequest(BaseModel):
    rows: List[ImportCommitRow]


class ImportCommitResult(BaseModel):
    inserted: int
    updated: int
    skipped: int


class ExportRequest(BaseModel):
    ids: List[int]


class PaperDeleteRequest(BaseModel):
    ids: List[int]


class BulkDeleteResult(BaseModel):
    deleted: int


class JobCreateRequest(BaseModel):
    ids: List[int] = Field(..., description="Paper IDs to include in the job")


class JobItemOut(BaseModel):
    id: int
    job_id: int
    paper_id: int
    paper_name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class JobSummaryOut(BaseModel):
    id: int
    job_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_count: int
    processed_count: int
    payload: Optional[Dict[str, Any]] = None
    result_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


class JobDetailOut(JobSummaryOut):
    items: List[JobItemOut] = Field(default_factory=list)


class JobQueueStateOut(BaseModel):
    paused: bool


class JobQueueStateUpdate(BaseModel):
    paused: bool


class JobQueueItemOut(BaseModel):
    job_id: int
    job_type: str
    item_id: int
    paper_id: int
    paper_name: Optional[str] = None
    status: str


class JobHistoryItemOut(BaseModel):
    job_id: int
    job_type: str
    job_status: str
    item_id: int
    paper_id: Optional[int] = None
    paper_name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class ResearchFeatureConfig(BaseModel):
    name: str
    keywords: list[str]
    desired_examples: int = Field(default=5, ge=1, le=50)


class ResearchEvidenceItem(BaseModel):
    paper_id: Optional[int] = None
    paper_name: Optional[str] = None
    source_type: str
    title: Optional[str] = None
    url: Optional[str] = None
    excerpt: Optional[str] = None
    matched_keywords: list[str] = Field(default_factory=list)


class ResearchFeature(BaseModel):
    id: int
    session_id: int
    name: str
    keywords: list[str]
    desired_examples: int
    status: str
    last_evaluated_at: Optional[datetime] = None
    evidence: dict = Field(default_factory=dict)
    error: Optional[str] = None


class ResearchSessionPaper(BaseModel):
    id: int
    paper_id: Optional[int] = None
    snapshot: dict = Field(default_factory=dict)


class ResearchSessionSummary(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    filter_params: dict = Field(default_factory=dict)
    query_string: Optional[str] = None
    paper_count: int
    feature_count: int


class ResearchSessionDetail(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    filter_params: dict = Field(default_factory=dict)
    query_string: Optional[str] = None
    papers: list[ResearchSessionPaper]
    features: list[ResearchFeature]


class ResearchSessionCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    paper_ids: list[int]
    filter_params: dict = Field(default_factory=dict)
    query_string: Optional[str] = None
    features: list[ResearchFeatureConfig] = Field(default_factory=list)


class ResearchSessionListResponse(BaseModel):
    items: list[ResearchSessionSummary]


class ResearchFeatureRunResponse(BaseModel):
    feature: ResearchFeature


class ResearchFeatureRunListResponse(BaseModel):
    features: list[ResearchFeature]
