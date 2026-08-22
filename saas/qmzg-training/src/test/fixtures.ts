import { Device, TrainingReport, TrainingSession, User } from '../api/types';

export const testUser: User = {
  id: 'user-1',
  email: 'demo@example.test',
  display_name: '验收用户',
  created_at: '2026-08-10T08:00:00Z',
  updated_at: null,
};

export const testDevice: Device = {
  id: 'device-real-12345678',
  product_id: 'product-1',
  display_name: '擎梦智骨外骨骼',
  created_at: '2026-08-10T08:00:00Z',
  updated_at: null,
};

export const testSession: TrainingSession = {
  id: 'session-1',
  external_session_id: 'acceptance_cloud_training_001',
  user_id: 'user-1',
  device_id: testDevice.id,
  started_at: '2026-08-10T08:00:00Z',
  ended_at: '2026-08-10T08:10:23Z',
  duration_sec: 623,
  total_reps: 57,
  avg_confidence: 9670,
  max_elbow_angle: 1285,
  max_shoulder_angle: 934,
  summary_json: { actions: { curl: 20, raise: 15, lateral: 12, boxing: 10 }, fault_count: 0 },
  training_type: 'active_assist',
  source_type: 'tuya_property',
  tuya_msg_id: 'message-1',
  created_at: '2026-08-10T08:10:25Z',
};

export const testReport: TrainingReport = {
  id: testSession.id,
  device_id: testDevice.id,
  training_time: testSession.started_at,
  duration_sec: 623,
  total_reps: 57,
  avg_confidence: 96.7,
  range_of_motion: { elbow_max: 128.5, shoulder_max: 93.4 },
  actions: [
    { name: 'curl', count: 20 },
    { name: 'raise', count: 15 },
    { name: 'lateral', count: 12 },
    { name: 'boxing', count: 10 },
  ],
  device_status: 'normal',
  fault_count: 0,
  training_type: 'active_assist',
  summary_json: testSession.summary_json || {},
  notice: '仅用于运动训练数据总结',
};
