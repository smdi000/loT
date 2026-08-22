import { TrainingType } from '../api/types';

const labels: Record<TrainingType, string> = {
  passive_assist: '被动助力训练',
  resistance: '抗阻训练',
  active_assist: '主动助力训练',
};

export function trainingTypeLabel(value: TrainingType | null | undefined): string {
  return value ? labels[value] : '--';
}

export default function TrainingTypeBadge({ value }: { value: TrainingType | null | undefined }) {
  const tone = value || 'unknown';
  return <span className={`training-type-badge training-type-${tone}`}>{trainingTypeLabel(value)}</span>;
}
