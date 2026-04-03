export interface Asteroid {
  spkid: number;
  name: string;
  a_au: number;
  eccentricity: number;
  inclination_deg: number;
  long_asc_node_deg: number | null;
  arg_perihelion_deg: number | null;
  mean_anomaly_deg: number | null;
  epoch_mjd: number | null;
  abs_magnitude: number | null;
  diameter_estimated_km: number | null;
  diameter_source: string | null;
  rotation_hours: number | null;
  albedo: number | null;
  neo: string | null;
  pha: string | null;
  orbit_class: string | null;
  moid_au: number | null;
  spectral_type: string | null;
  delta_v_km_s: number | null;
  tisserand_jupiter: number | null;
  inclination_penalty: number | null;
  orbital_precision_source: string | null;
  surface_gravity_m_s2: number | null;
  rotation_feasibility: number | null;
  regolith_likelihood: number | null;
  composition_class: string | null;
  composition_source: string | null;
  resource_value_usd_per_kg: number | null;
  specimen_value_per_kg: number | null;
  estimated_mass_kg: number | null;
  mission_cost_usd_per_kg: number | null;
  margin_per_kg: number | null;
  break_even_kg: number | null;
  is_viable: boolean;
  missions_supported: number | null;
  mission_profit_usd: number | null;
  campaign_profit_usd: number | null;
  economic_score: number | null;
  economic_priority_rank: number | null;
  total_extractable_precious_kg: number | null;
  total_precious_value_usd: number | null;
}

export interface AsteroidListResponse {
  total: number;
  limit: number;
  offset: number;
  data: Asteroid[];
}

export interface Stats {
  total_objects: number;
  scored_objects: number;
  nea_candidates: number;
  min_delta_v: number;
  max_delta_v: number;
  median_delta_v: number;
  avg_delta_v: number;
}

export interface HistogramBin {
  bin_floor_km_s: number;
  count: number;
}

export interface CompositionStat {
  class: string;
  count: number;
  viable: number;
  total_profit: number;
}

export interface Filters {
  neo?: string;
  is_viable?: boolean;
  composition_class?: string;
  orbit_class?: string;
  dv_min?: number;
  dv_max?: number;
  sort: string;
  order: 'asc' | 'desc';
  limit: number;
  offset: number;
}
