import { summarizeSessions } from '../utils/dashboard';
import { testSession } from './fixtures';

test('dashboard data transform computes real session aggregates', () => {
  const older = { ...testSession, id: 'older', total_reps: 10, duration_sec: 60, created_at: '2026-08-09T00:00:00Z' };
  const summary = summarizeSessions([older, testSession]);
  expect(summary.trainingCount).toBe(2);
  expect(summary.totalReps).toBe(67);
  expect(summary.totalDuration).toBe(683);
  expect(summary.latest?.external_session_id).toBe('acceptance_cloud_training_001');
});

test('dashboard data transform supports an empty dataset', () => {
  expect(summarizeSessions([])).toEqual({
    trainingCount: 0,
    totalReps: 0,
    totalDuration: 0,
    latest: null,
    recent: [],
  });
});
