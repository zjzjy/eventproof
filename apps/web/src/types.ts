export type ClaimType =
  | "fact"
  | "opinion"
  | "speculation"
  | "rumor"
  | "denial"
  | "correction";

export type ClaimStatus = "active" | "denied" | "unverified" | "superseded";

export type Claim = {
  id: string;
  event_id: string;
  document_id: string;
  text: string;
  claim_type: ClaimType;
  claim_role: string;
  subject: string;
  predicate: string;
  object: string;
  value: string | null;
  unit: string;
  quote: string;
  hedge: string;
  confidence: number;
  status: ClaimStatus;
  strength: number;
  strength_band: "strong" | "medium" | "weak";
  strength_json: Record<string, number>;
  strength_explanation: string;
  introduced_at: string;
  is_inferred: boolean;
  source_tier: string;
};

export type Document = {
  id: string;
  event_id: string;
  title: string;
  doc_type: string;
  source: string;
  source_tier: string;
  published_at: string;
  occurred_at: string | null;
  time_precision: string;
  url: string;
  ingested_at: string;
  data_origin: string;
  claim_count: number;
  claims: Claim[];
};

export type Revision = {
  id: string;
  event_id: string;
  version: number;
  knowledge_at: string;
  summary: string;
  verification_status: string;
  lifecycle_status: string;
  impact_status: string;
  evidence_strength: number;
  status_detail: Record<string, string>;
  claim_ids: string[];
  changed_fields: string[];
  reason: string;
  trigger_document_id: string;
  is_inferred: boolean;
  created_at: string;
};

export type MergeDecision = {
  id: string;
  event_id: string;
  document_id: string;
  document_title: string;
  relation: string;
  score: number;
  decision: string;
  shared_slots: Record<string, string>;
  differences: string[];
  reason: string;
  model: string;
  created_at: string;
};

export type EventDetail = {
  id: string;
  storyline_id: string;
  title: string;
  event_type: string;
  primary_entity: string;
  security_code: string;
  exchange: string;
  occurred_at: string;
  occurred_precision: string;
  disclosed_at: string;
  disclosed_precision: string;
  first_ingested_at: string;
  updated_at: string;
  verification_status: string;
  lifecycle_status: string;
  impact_status: string;
  status_detail: Record<string, string>;
  evidence_strength: number;
  summary: string;
  current_revision_id: string;
  data_as_of: string;
  revision: Revision;
  revisions: Revision[];
  claims: Claim[];
  documents: Document[];
  merge_decisions: MergeDecision[];
  as_of: string | null;
  is_replay: boolean;
  sources_count: number;
  independent_sources_count: number;
  denied_claims_count: number;
  active_claims_count: number;
  available_as_of: Array<{
    version: number;
    label: string;
    knowledge_at: string;
    summary: string;
  }>;
};

export type EventSummary = {
  id: string;
  title: string;
  primary_entity: string;
  security_code: string;
  event_type: string;
  summary: string;
  verification_status: string;
  lifecycle_status: string;
  impact_status: string;
  status_detail: Record<string, string>;
  evidence_strength: number;
  updated_at: string;
  sources_count: number;
  denied_claims_count: number;
  revision_count: number;
};

export type Notification = {
  id: string;
  event_id: string;
  revision_id: string;
  level: "P0" | "P1" | "P2";
  title: string;
  body: string;
  why: string;
  created_at: string;
  read_at: string | null;
  diff_json: Record<string, unknown>;
};

export type Diff = {
  from: Revision;
  to: Revision;
  added: Claim[];
  removed: Claim[];
  status_changes: Array<{ claim: Claim; from: ClaimStatus; to: ClaimStatus }>;
  changed_fields: string[];
  summary_from: string;
  summary_to: string;
  reason: string;
  trigger_document_id: string;
};

export type Meta = {
  model: string;
  prompt_version: string;
  total_cost_cny: number;
  data_note: string;
  curation: string;
  service: string;
  version: string;
  data_mode: string;
};

