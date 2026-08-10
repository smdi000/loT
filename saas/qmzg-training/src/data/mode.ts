export type DataMode = 'mock' | 'real';

export function getDataMode(): DataMode {
  return process.env.QMZG_DATA_MODE === 'mock' ? 'mock' : 'real';
}

export function isMockDataMode(): boolean {
  return getDataMode() === 'mock';
}

