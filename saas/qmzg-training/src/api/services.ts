import api from './client';
import { AccessToken, Device, TrainingReport, TrainingSession, TrainingSessionPage, User } from './types';
import { isMockDataMode } from '../data/mode';
import { mockDataProvider } from '../data/mockProvider';

export async function login(email: string, password: string): Promise<AccessToken> {
  if (isMockDataMode()) return mockDataProvider.login(email, password);
  return (await api.post<AccessToken>('/api/auth/login', { email, password })).data;
}

export async function getMe(): Promise<User> {
  if (isMockDataMode()) return mockDataProvider.getMe();
  return (await api.get<User>('/api/me')).data;
}

export async function getDevices(): Promise<Device[]> {
  if (isMockDataMode()) return mockDataProvider.getDevices();
  return (await api.get<Device[]>('/api/devices')).data;
}

export async function bindDevice(deviceId: string): Promise<{ device_id: string; bound: boolean }> {
  if (isMockDataMode()) return mockDataProvider.bindDevice(deviceId);
  return (await api.post('/api/devices/bind', { device_id: deviceId })).data;
}

export async function unbindDevice(deviceId: string): Promise<void> {
  if (isMockDataMode()) return mockDataProvider.unbindDevice(deviceId);
  await api.delete(`/api/devices/${encodeURIComponent(deviceId)}/bind`);
}

export async function getTrainingSessions(
  page = 1,
  pageSize = 20,
  deviceId?: string
): Promise<TrainingSessionPage> {
  if (isMockDataMode()) return mockDataProvider.getTrainingSessions(page, pageSize, deviceId);
  return (
    await api.get<TrainingSessionPage>('/api/training-sessions', {
      params: { page, page_size: pageSize, ...(deviceId ? { device_id: deviceId } : {}) },
    })
  ).data;
}

export async function getAllTrainingSessions(deviceId?: string): Promise<TrainingSession[]> {
  const first = await getTrainingSessions(1, 100, deviceId);
  const items = [...first.items];
  const pages = Math.ceil(first.total / 100);
  for (let page = 2; page <= pages; page += 1) {
    items.push(...(await getTrainingSessions(page, 100, deviceId)).items);
  }
  return items;
}

export async function getTrainingSession(id: string): Promise<TrainingSession> {
  if (isMockDataMode()) return mockDataProvider.getTrainingSession(id);
  return (await api.get<TrainingSession>(`/api/training-sessions/${encodeURIComponent(id)}`)).data;
}

export async function getTrainingReport(id: string): Promise<TrainingReport> {
  if (isMockDataMode()) return mockDataProvider.getTrainingReport(id);
  return (
    await api.get<TrainingReport>(`/api/training-sessions/${encodeURIComponent(id)}/report`)
  ).data;
}
