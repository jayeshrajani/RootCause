// Mirrors apps/api/app/schemas/triage.py. Keep both in sync (see docs/api-contract.md).

export const CROPS = [
  "rice",
  "wheat",
  "maize",
  "cotton",
  "sugarcane",
  "soybean",
  "groundnut",
  "chickpea",
  "tomato",
  "potato",
  "onion",
  "chilli",
  "other",
] as const;
export type Crop = (typeof CROPS)[number];

export const SYMPTOM_DURATIONS = [
  "less_than_3_days",
  "3_to_7_days",
  "1_to_2_weeks",
  "more_than_2_weeks",
  "not_sure",
] as const;
export type SymptomDuration = (typeof SYMPTOM_DURATIONS)[number];

export type AnalysisMode = "mock" | "ai";
export type ResponseLanguage = "en" | "hi" | "pa" | "es" | "fr";
export type TriageStatus = "completed" | "insufficient_information";
export type UrgencyLevel = "low" | "moderate" | "high" | "critical";
export type ConfidenceLevel = "low" | "medium" | "high";
export type SourceKind =
  | "farmer_report"
  | "photo"
  | "weather"
  | "satellite"
  | "knowledge_base"
  | "analysis_engine"
  | "reference_photos";
export type EvidenceAvailability = "available" | "unavailable" | "not_integrated";
export type DataSourceStatus =
  | "used"
  | "received_not_analysed"
  | "unavailable"
  | "not_integrated";
export type ActionPriority = "immediate" | "within_days" | "monitor";

export interface Evidence {
  id: string;
  source: SourceKind;
  availability: EvidenceAvailability;
  observation: string;
  observed_at: string | null;
}

export interface PossibleCause {
  name: string;
  explanation: string;
  supporting_evidence: string[];
  contradictory_evidence: string[];
  confidence: ConfidenceLevel;
  uncertainty_note: string;
  analysis_score: number | null;
  weather_score: number | null;
  reference_score?: number | null;
  evidence_fit_score: number | null;
}

export interface MissingInformation {
  item: string;
  reason: string;
}

export interface RecommendedAction {
  action: string;
  rationale: string;
  priority: ActionPriority;
  requires_expert_verification: boolean;
  addresses: string | null;
  analysis_score: number | null;
  weather_score: number | null;
  evidence_fit_score: number | null;
}

export interface DataSource {
  id: string;
  name: string;
  kind: SourceKind;
  status: DataSourceStatus;
  description: string;
  retrieved_at: string | null;
}

export interface TriageResponse {
  report_id: string;
  status: TriageStatus;
  analysis_mode: AnalysisMode;
  response_language: ResponseLanguage;
  crop: Crop | null;
  detected_crop: string | null;
  location_label: string | null;
  approximate_location: string | null;
  weather_summary: string | null;
  reference_weight?: number | null;
  summary: string;
  urgency: UrgencyLevel;
  urgency_reason: string;
  possible_causes: PossibleCause[];
  evidence: Evidence[];
  missing_information: MissingInformation[];
  recommended_actions: RecommendedAction[];
  requires_expert_review: boolean;
  generated_at: string;
  data_sources: DataSource[];
  disclaimer: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: { field: string | null; message: string }[];
  };
}
