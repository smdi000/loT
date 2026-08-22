export interface AccessToken {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string | null;
  display_name: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface Device {
  id: string;
  product_id: string | null;
  display_name: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface TrainingSession {
  id: string;
  external_session_id: string;
  user_id: string | null;
  device_id: string;
  started_at: string | null;
  ended_at: string | null;
  duration_sec: number | null;
  total_reps: number | null;
  avg_confidence: number | null;
  max_elbow_angle: number | null;
  max_shoulder_angle: number | null;
  summary_json: Record<string, unknown> | null;
  training_type: TrainingType | null;
  source_type: 'tuya_property' | 'tuya_event' | 'mock';
  tuya_msg_id: string | null;
  created_at: string;
}

export interface TrainingSessionPage {
  items: TrainingSession[];
  page: number;
  page_size: number;
  total: number;
}

export interface TrainingAction {
  name: string;
  count: number;
}

export type TrainingType = 'passive_assist' | 'resistance' | 'active_assist';

export interface TrainingReport {
  id: string;
  device_id: string;
  training_time: string | null;
  duration_sec: number;
  total_reps: number;
  avg_confidence: number;
  range_of_motion: { elbow_max: number; shoulder_max: number };
  actions: TrainingAction[];
  device_status: string | null;
  fault_count: number | null;
  training_type: TrainingType | null;
  summary_json: Record<string, unknown>;
  notice: string;
}

export interface FastApiError {
  detail?: string | Array<{ msg?: string }>;
}
