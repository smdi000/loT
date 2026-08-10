export function maskDeviceId(deviceId: string): string {
  if (deviceId.length <= 8) return `••••${deviceId.slice(-4)}`;
  return `${deviceId.slice(0, 4)}••••••${deviceId.slice(-4)}`;
}

export function formatDate(value?: string | null): string {
  if (!value) return '暂无记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '暂无记录';
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date);
}

export function formatDuration(seconds?: number | null): string {
  const safe = Math.max(0, seconds || 0);
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return minutes ? `${minutes} 分 ${rest} 秒` : `${rest} 秒`;
}

export function formatConfidence(raw?: number | null): string {
  if (raw === null || raw === undefined) return '--';
  return `${(raw / 100).toFixed(2)}%`;
}
