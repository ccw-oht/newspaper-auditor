export type AuditValue = 'Yes' | 'No' | 'Manual Review' | 'Manual Review (Timeout)' | 'Manual Review (Error)' | string;

export interface AuditSummary {
  id: number | null;
  timestamp: string | null;
  has_pdf: AuditValue | null;
  pdf_only: AuditValue | null;
  paywall: AuditValue | null;
  notices: AuditValue | null;
  responsive: AuditValue | null;
  sources: string | null;
  notes: string | null;
  homepage_preview: string | null;
  chain_owner: string | null;
  cms_platform: string | null;
  cms_vendor: string | null;
  overrides?: Record<string, AuditValue | null | string | undefined> | null;
}

export interface AuditOut extends AuditSummary {
  id: number;
  paper_id: number;
  timestamp: string;
  homepage_html: string | null;
  chain_owner: string | null;
  cms_platform: string | null;
  cms_vendor: string | null;
}

export interface PaperSummary {
  id: number;
  state: string | null;
  city: string | null;
  paper_name: string | null;
  website_url: string | null;
  phone: string | null;
  email: string | null;
  mailing_address: string | null;
  county: string | null;
  chain_owner: string | null;
  cms_platform: string | null;
  cms_vendor: string | null;
  extra_data: Record<string, unknown> | null;
  audit_overrides: Record<string, AuditValue | null | string | undefined> | null;
  latest_audit: AuditSummary | null;
}

export interface PaperListResponse {
  total: number;
  items: PaperSummary[];
  options: PaperListOptions;
}

export interface PaperDetail {
  id: number;
  state: string | null;
  city: string | null;
  paper_name: string | null;
  website_url: string | null;
  phone: string | null;
  email: string | null;
  mailing_address: string | null;
  county: string | null;
  chain_owner: string | null;
  cms_platform: string | null;
  cms_vendor: string | null;
  extra_data: Record<string, unknown> | null;
  audit_overrides: Record<string, AuditValue | null | string | undefined> | null;
  latest_audit: AuditSummary | null;
  audits: AuditOut[];
}

export interface PaperUpdatePayload {
  state?: string | null;
  city?: string | null;
  paper_name?: string | null;
  website_url?: string | null;
  phone?: string | null;
  email?: string | null;
  mailing_address?: string | null;
  county?: string | null;
  chain_owner?: string | null;
  cms_platform?: string | null;
  cms_vendor?: string | null;
  extra_data?: Record<string, unknown> | null;
  audit_overrides?: Record<string, AuditValue | null | string | undefined> | null;
}

export interface PaperListParams {
  state?: string;
  city?: string;
  has_pdf?: string;
  pdf_only?: string;
  paywall?: string;
  notices?: string;
  responsive?: string;
  chain_owner?: string;
  cms_platform?: string;
  cms_vendor?: string;
  q?: string;
  sort?: string;
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface FilterValues {
  state?: string;
  city?: string;
  has_pdf?: string;
  pdf_only?: string;
  paywall?: string;
  notices?: string;
  responsive?: string;
  chain_owner?: string;
  cms_platform?: string;
  cms_vendor?: string;
  q?: string;
  limit?: number;
}

export interface LookupResult {
  paper_id: number;
  updated: boolean;
  phone: string | null;
  email: string | null;
  mailing_address: string | null;
  lookup_metadata: Record<string, unknown> | null;
  error: string | null;
}

export interface PaperListOptions {
  states: string[];
  cities: string[];
  chainOwners: string[];
  cmsPlatforms: string[];
  cmsVendors: string[];
}

export interface PaperIdList {
  total: number;
  ids: number[];
}

export interface ImportPreviewRow {
  temp_id: string;
  status: string;
  allowed_actions: string[];
  data: Record<string, unknown>;
  existing: Record<string, unknown> | null;
  differences: Record<string, { old: unknown; new: unknown }>;
  issues: string[];
}

export interface ImportPreviewSummary {
  new: number;
  update: number;
  duplicate: number;
  invalid: number;
}

export interface ImportPreviewResponse {
  rows: ImportPreviewRow[];
  summary: ImportPreviewSummary;
}

export interface ImportCommitRow {
  temp_id: string;
  action: string;
  data: Record<string, unknown>;
  existing_id?: number | null;
  status?: string | null;
}

export interface ImportCommitRequest {
  rows: ImportCommitRow[];
}

export interface ImportCommitResult {
  inserted: number;
  updated: number;
  skipped: number;
}

export interface BulkDeleteResult {
  deleted: number;
}

export interface ResearchFeatureConfig {
  name: string;
  keywords: string[];
  desired_examples?: number;
}

export interface ResearchEvidenceItem {
  paper_id: number | null;
  paper_name: string | null;
  source_type: string;
  title: string | null;
  url: string | null;
  excerpt: string | null;
  matched_keywords: string[];
}

export interface ResearchFeature {
  id: number;
  session_id: number;
  name: string;
  keywords: string[];
  desired_examples: number;
  status: string;
  last_evaluated_at: string | null;
  evidence: {
    matches: ResearchEvidenceItem[];
    [key: string]: unknown;
  };
  error?: string | null;
}

export interface ResearchSessionPaperSnapshot {
  id: number;
  paper_id: number | null;
  snapshot: Record<string, unknown>;
}

export interface ResearchSessionSummary {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  filter_params: Record<string, unknown>;
  query_string?: string | null;
  paper_count: number;
  feature_count: number;
}

export interface ResearchSessionDetail {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  filter_params: Record<string, unknown>;
  query_string?: string | null;
  papers: ResearchSessionPaperSnapshot[];
  features: ResearchFeature[];
}

export interface ResearchSessionListResponse {
  items: ResearchSessionSummary[];
}

export interface ResearchSessionCreatePayload {
  name: string;
  description?: string;
  paper_ids: number[];
  filter_params: Record<string, unknown>;
  query_string?: string;
  features: ResearchFeatureConfig[];
}
