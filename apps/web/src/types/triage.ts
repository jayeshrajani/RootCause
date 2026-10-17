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
  condition_key?: string | null;
  explanation: string;
  supporting_evidence: string[];
  contradictory_evidence: string[];
  confidence: ConfidenceLevel;
  uncertainty_note: string;
  analysis_score: number | null;
  weather_score: number | null;
  reference_score?: number | null;
  satellite_score?: number | null;
  evidence_fit_score: number | null;
  evidence_ledger?: EvidenceContribution[];
}

export type EvidenceEffect = "supports" | "weighs_against" | "neutral";

/** Rule-based weather/satellite adjustment to a cause's evidence fit. */
export interface EvidenceContribution {
  signal: "weather" | "satellite";
  effect: EvidenceEffect;
  points: number;
  reason: string;
}

export type WeatherPattern = "wet" | "hot_dry" | "cold" | "humid" | "dry" | "mild";

export interface WeatherFacts {
  days: number;
  start: string;
  end: string;
  temp_min_c: number;
  temp_max_c: number;
  temp_mean_c: number;
  rain_total_mm: number;
  wet_days: number;
  humid_days: number;
  hot_days: number;
  cold_nights: number;
  pattern: WeatherPattern;
}

export interface CropIdentification {
  crop: Crop | null;
  confidence: ConfidenceLevel;
  needs_confirmation: boolean;
  candidates: Crop[];
  image_quality: string;
  reference_agreement: "agrees" | "disagrees" | "not_covered" | "unavailable";
  analysis_mode: AnalysisMode;
}

export type SatelliteStatus =
  | "available"
  | "insufficient_data"
  | "unavailable"
  | "not_configured"
  | "not_requested";
export type VegetationTrend = "improving" | "stable" | "declining" | "unknown";
export type SatelliteLimitation =
  | "approximate_area"
  | "approximate_location"
  | "no_baseline"
  | "single_observation"
  | "partial_coverage"
  | "stale_observation"
  | "low_vegetation";

export interface SatelliteWindow {
  start: string;
  end: string;
  clear_observations: number;
  ndvi_median: number | null;
  ndmi_median: number | null;
}

/** Sentinel-2 vegetation evidence (Google Earth Engine). Supporting evidence, never a diagnosis. */
export interface SatelliteAnalysis {
  status: SatelliteStatus;
  source: string;
  dataset: string;
  analysis_date: string | null;
  sampling_method: "buffer" | "field_boundary" | null;
  buffer_m: number | null;
  sampling_area_ha: number | null;
  ndvi: number | null;
  ndmi: number | null;
  ndvi_change: number | null;
  ndmi_change: number | null;
  trend: VegetationTrend;
  ndmi_trend: VegetationTrend;
  observation_date: string | null;
  observation_age_days: number | null;
  valid_pixel_coverage: number | null;
  recent_window: SatelliteWindow | null;
  baseline_window: SatelliteWindow | null;
  interpretable: boolean;
  limitations: SatelliteLimitation[];
  reason: string | null;
  message: string | null;
  retrieved_at: string | null;
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
  weather_facts?: WeatherFacts | null;
  satellite?: SatelliteAnalysis | null;
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

export interface ActiveIngredient {
  name: string;
  kind: "fungicide" | "insecticide" | "bactericide" | "biological" | "nutrient" | "other";
  note: string;
}

export interface TreatmentPlan {
  crop: string;
  cause: string;
  confirm_first: boolean;
  non_chemical_steps: string[];
  active_ingredients: ActiveIngredient[];
  safety: string[];
  expert_note: string;
  response_language: ResponseLanguage;
}

export interface Shop {
  name: string;
  address: string | null;
  offers: string | null;
  maps_uri: string | null;
  place_id: string | null;
}
