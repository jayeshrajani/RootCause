import type { Crop, SymptomDuration } from "@/types/triage";

export const CROP_LABELS: Record<Crop, string> = {
  rice: "Rice",
  wheat: "Wheat",
  maize: "Maize",
  cotton: "Cotton",
  sugarcane: "Sugarcane",
  soybean: "Soybean",
  groundnut: "Groundnut",
  chickpea: "Chickpea",
  tomato: "Tomato",
  potato: "Potato",
  onion: "Onion",
  chilli: "Chilli",
  other: "Something else",
};

export const CROP_SCIENTIFIC: Record<Crop, string> = {
  rice: "Oryza sativa",
  wheat: "Triticum aestivum",
  maize: "Zea mays",
  cotton: "Gossypium spp.",
  sugarcane: "Saccharum officinarum",
  soybean: "Glycine max",
  groundnut: "Arachis hypogaea",
  chickpea: "Cicer arietinum",
  tomato: "Solanum lycopersicum",
  potato: "Solanum tuberosum",
  onion: "Allium cepa",
  chilli: "Capsicum annuum",
  other: "Not listed here",
};

export const SYMPTOM_PHRASES = [
  "Yellowing leaves",
  "Brown or black spots",
  "Wilting or drooping",
  "Holes in leaves",
  "White or grey powder",
  "Curling leaves",
  "Dry, burnt edges",
  "Stunted growth",
  "Rotting stem or fruit",
  "Insects visible",
] as const;

export const SYMPTOM_DURATION_LABELS: Record<SymptomDuration, string> = {
  less_than_3_days: "Less than 3 days",
  "3_to_7_days": "3 to 7 days",
  "1_to_2_weeks": "1 to 2 weeks",
  more_than_2_weeks: "More than 2 weeks",
  not_sure: "Not sure",
};

// Must match apps/api settings (ROOTCAUSE_MAX_IMAGES / ROOTCAUSE_MAX_IMAGE_BYTES).
export const MAX_IMAGES = 3;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;

export const DESCRIPTION_MAX = 2000;
export const LOCATION_LABEL_MAX = 120;
