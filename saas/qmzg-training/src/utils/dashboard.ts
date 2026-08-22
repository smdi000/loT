import { TrainingSession } from '../api/types';

export interface DashboardSummary {
  trainingCount: number;
  totalReps: number;
  totalDuration: number;
  latest: TrainingSession | null;
  recent: TrainingSession[];
}

export function summarizeSessions(sessions: TrainingSession[]): DashboardSummary {
  const ordered = [...sessions].sort(
    (left, right) =>
      new Date(right.started_at || right.created_at).getTime() -
      new Date(left.started_at || left.created_at).getTime()
  );
  return {
    trainingCount: ordered.length,
    totalReps: ordered.reduce((sum, item) => sum + (item.total_reps || 0), 0),
    totalDuration: ordered.reduce((sum, item) => sum + (item.duration_sec || 0), 0),
    latest: ordered[0] || null,
    recent: ordered.slice(0, 5),
  };
}
