import { ComplaintStatus } from "./enums";

export interface ComplaintExtraction {
  trip_time?: string;
  pickup_location?: string;
  drop_location?: string;
  quoted_amount?: number;
  paid_amount?: number;
  platform?: string;
}

export interface PatternResult {
  is_pattern: boolean;
  cluster_id: string;
  similar_complaint_count: number;
  common_route: string;
  common_time_window: string;
  confidence_score: number;
  location_score: number;
  platform_score: number;
  time_score: number;
}

export interface ServiceStatus {
  rime: string;
  qdrant: string;
  pattern_source: string;
}

export type { ComplaintStatus };

export interface VoiceComplaintResponse {
  status: ComplaintStatus;
  transcript: string;
  feedback: string;
  audio_base64?: string | null;
  audio_mime?: string | null;
  extraction?: ComplaintExtraction | null;
  missing_fields: string[];
  pattern?: PatternResult | null;
  complaint_id?: string | null;
  service_status?: ServiceStatus;
}

export interface ComplaintRecord {
  complaint_id: string;
  driver_id_hash?: string | null;
  platform: string;
  trip_timestamp?: string | null;
  pickup_location?: string | null;
  drop_location?: string | null;
  quoted_amount?: number | null;
  paid_amount?: number | null;
  discrepancy?: number | null;
  discrepancy_pct?: number | null;
  raw_transcript: string;
  cluster_id?: string | null;
  cluster_size: number;
  cluster_confidence: number;
  created_at: string;
}

export interface DashboardPattern {
  cluster_id: string;
  count: number;
  route: string;
  time_window: string;
  avg_discrepancy_pct: number;
}

export interface DashboardStats {
  total_complaints: number;
  pattern_clusters: number;
  top_patterns: DashboardPattern[];
}
