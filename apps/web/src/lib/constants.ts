import type { Crop } from "@/types/triage";

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

export const CROP_LOCAL_NAMES: Record<Crop, string | null> = {
  rice: "Dhan / Chawal",
  wheat: "Gehun",
  maize: "Makka",
  cotton: "Kapas",
  sugarcane: "Ganna",
  soybean: "Soyabean",
  groundnut: "Moongphali",
  chickpea: "Chana",
  tomato: "Tamatar",
  potato: "Aloo",
  onion: "Pyaz",
  chilli: "Mirchi",
  other: null,
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

// Must match apps/api settings (ROOTCAUSE_MAX_IMAGES / ROOTCAUSE_MAX_IMAGE_BYTES).
export const MAX_IMAGES = 3;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;

export const DESCRIPTION_MAX = 2000;
export const LOCATION_LABEL_MAX = 120;
