import {
  AccessToken,
  Device,
  TrainingReport,
  TrainingSession,
  TrainingSessionPage,
  User,
} from '../api/types';

const mockUser: User = {
  id: 'demo-user-001',
  email: 'demo@qmzg.example',
  display_name: '演示用户',
  created_at: '2026-08-11T08:00:00Z',
  updated_at: null,
};

const mockDevice: Device = {
  id: 'DEMO-DEVICE-001',
  product_id: 'DEMO-PRODUCT-001',
  display_name: '擎梦智骨演示外骨骼',
  created_at: '2026-08-11T08:00:00Z',
  updated_at: null,
};

const mockSession: TrainingSession = {
  id: 'demo-session-row-001',
  external_session_id: 'demo_session_001',
  user_id: mockUser.id,
  device_id: mockDevice.id,
  started_at: '2026-08-11T08:00:00Z',
  ended_at: '2026-08-11T08:10:23Z',
  duration_sec: 623,
  total_reps: 57,
  avg_confidence: 9670,
  max_elbow_angle: 1285,
  max_shoulder_angle: 934,
  summary_json: {
    training_type: 'active_assist',
    actions: { curl: 20, raise: 15, lateral: 12, boxing: 10 },
    fault_count: 0,
  },
  training_type: 'active_assist',
  source_type: 'mock',
  tuya_msg_id: null,
  created_at: '2026-08-11T08:10:25Z',
};

let deviceBound = true;

function copySession(): TrainingSession {
  return JSON.parse(JSON.stringify(mockSession)) as TrainingSession;
}

export const mockDataProvider = {
  async login(email: string, password: string): Promise<AccessToken> {
    if (!email.trim() || !password) {
      throw new Error('Mock Mode 仍要求输入非空账号和密码，以保留登录交互。');
    }
    return { access_token: 'mock-access-token', token_type: 'bearer' };
  },

  async getMe(): Promise<User> {
    return { ...mockUser };
  },

  async getDevices(): Promise<Device[]> {
    return deviceBound ? [{ ...mockDevice }] : [];
  },

  async bindDevice(deviceId: string): Promise<{ device_id: string; bound: boolean }> {
    if (deviceId !== mockDevice.id) {
      throw new Error(`Mock Mode 仅提供演示设备 ${mockDevice.id}`);
    }
    deviceBound = true;
    return { device_id: mockDevice.id, bound: true };
  },

  async unbindDevice(deviceId: string): Promise<void> {
    if (deviceId === mockDevice.id) deviceBound = false;
  },

  async getTrainingSessions(page: number, pageSize: number, deviceId?: string): Promise<TrainingSessionPage> {
    const visible = !deviceId || deviceId === mockDevice.id ? [copySession()] : [];
    const start = (page - 1) * pageSize;
    return { items: visible.slice(start, start + pageSize), page, page_size: pageSize, total: visible.length };
  },

  async getTrainingSession(id: string): Promise<TrainingSession> {
    if (id !== mockSession.id) throw new Error('Mock training session not found');
    return copySession();
  },

  async getTrainingReport(id: string): Promise<TrainingReport> {
    if (id !== mockSession.id) throw new Error('Mock training report not found');
    return {
      id: mockSession.id,
      device_id: mockDevice.id,
      training_time: mockSession.started_at,
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
      device_status: null,
      fault_count: 0,
      training_type: mockSession.training_type,
      summary_json: { ...(mockSession.summary_json || {}) },
      notice: '训练数据分析仅用于运动训练信息展示，不构成医疗诊断或治疗建议。',
    };
  },

  reset(): void {
    deviceBound = true;
  },
};
