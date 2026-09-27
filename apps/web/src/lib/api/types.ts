// Wire types for the AIA API routes the settings page uses.
// Mirrors apps/api/src/aia_api/schemas/settings.py and routers/scope.py.
// Enum *values* are never listed here: they arrive in `vocabularies`.

export type SettingControl = "API" | "DEPLOYMENT" | "CODE" | "INVARIANT";

// `null` means "not configured" -- never zero, never false.
export type SettingValue = string | number | boolean | string[] | null;

export type SettingItem = {
  key: string;
  value: SettingValue;
  control: SettingControl;
  source: string;
  unit: string | null;
};

export type SettingGroup = { key: string; items: SettingItem[] };

export type Vocabularies = {
  organization_roles: string[];
  scope_roles: { role: string; permissions: string[] }[];
  permissions: string[];
  client_statuses: string[];
  study_statuses: string[];
  providers: { id: string; label: string; paid: boolean }[];
  provider_policies: string[];
  model_capabilities: string[];
  data_classes: string[];
  research_stages: { id: string; label: string | null }[];
  simulation_stages: { id: string; label: string | null }[];
};

export type SettingsDocument = {
  organization_id: string;
  your_role: string;
  may_administer: boolean;
  groups: SettingGroup[];
  vocabularies: Vocabularies;
};

export type Member = {
  user_id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  organization_role: string;
};

export type Client = {
  client_id: string;
  slug: string;
  name: string;
  status: string;
  reference: string;
  study_count: number;
  created_at: string | null;
};

// Budget figures are absent (null) when the caller may not view costs -- not zero.
export type Study = {
  study_id: string;
  client_id: string;
  slug: string;
  name: string;
  status: string;
  accepts_work: boolean;
  your_role: string | null;
  budget_usd: number | null;
  spent_usd: number | null;
  remaining_usd: number | null;
  created_at: string | null;
  modified_at: string | null;
  delivered_at: string | null;
};

export type SelfApprovalLevels = {
  organization: boolean | null;
  clients: { client_id: string; allowed: boolean }[];
  studies: { study_id: string; client_id: string; allowed: boolean }[];
};

export type AuditEntry = {
  event_id: number;
  action: string;
  client_id: string | null;
  study_id: string | null;
  subject_user_id: string | null;
  actor_id: string | null;
  role: string | null;
  reason: string;
  created_at: string | null;
};

export type Health = { status: string; [key: string]: unknown };
