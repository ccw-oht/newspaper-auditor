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
  mailing_address: string | null;
  county: string | null;
  extra_data: Record<string, unknown> | null;
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
  mailing_address: string | null;
  county: string | null;
  extra_data: Record<string, unknown> | null;
  latest_audit: AuditSummary | null;
  audits: AuditOut[];
}

export interface PaperUpdatePayload {
  state?: string | null;
  city?: string | null;
  paper_name?: string | null;
  website_url?: string | null;
  phone?: string | null;
  mailing_address?: string | null;
  county?: string | null;
  extra_data?: Record<string, unknown> | null;
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

export interface PaperListOptions {
  states: string[];
  cities: string[];
  chainOwners: string[];
  cmsPlatforms: string[];
  cmsVendors: string[];
}
