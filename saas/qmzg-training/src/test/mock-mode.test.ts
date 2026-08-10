import api from '../api/client';
import {
  getDevices,
  getTrainingReport,
  getTrainingSessions,
  login,
} from '../api/services';
import { mockDataProvider } from '../data/mockProvider';

const originalMode = process.env.QMZG_DATA_MODE;

beforeEach(() => {
  process.env.QMZG_DATA_MODE = 'mock';
  mockDataProvider.reset();
});

afterEach(() => {
  jest.restoreAllMocks();
});

afterAll(() => {
  process.env.QMZG_DATA_MODE = originalMode;
});

test('mock mode provides clearly labelled demo data without calling real API', async () => {
  const getSpy = jest.spyOn(api, 'get');
  const postSpy = jest.spyOn(api, 'post');

  const token = await login('ui-teammate@example.test', 'non-empty-local-input');
  const devices = await getDevices();
  const sessions = await getTrainingSessions();
  const report = await getTrainingReport('demo-session-row-001');

  expect(token.access_token).toBe('mock-access-token');
  expect(devices[0].id).toBe('DEMO-DEVICE-001');
  expect(sessions.items[0].external_session_id).toBe('demo_session_001');
  expect(sessions.items[0].source_type).toBe('mock');
  expect(report).toMatchObject({
    duration_sec: 623,
    total_reps: 57,
    avg_confidence: 96.7,
    range_of_motion: { elbow_max: 128.5, shoulder_max: 93.4 },
    fault_count: 0,
  });
  expect(getSpy).not.toHaveBeenCalled();
  expect(postSpy).not.toHaveBeenCalled();
});

test('real mode remains the default when the variable is absent', () => {
  delete process.env.QMZG_DATA_MODE;
  jest.resetModules();
  const { getDataMode } = require('../data/mode') as typeof import('../data/mode');
  expect(getDataMode()).toBe('real');
});
