import { render, screen } from '@testing-library/react';
import TrainingTypeBadge from '../components/TrainingTypeBadge';

test('renders all canonical training type labels and a neutral null marker', () => {
  render(
    <div>
      <TrainingTypeBadge value="active_assist" />
      <TrainingTypeBadge value="resistance" />
      <TrainingTypeBadge value="passive_assist" />
      <TrainingTypeBadge value={null} />
    </div>
  );
  expect(screen.getByText('主动助力训练')).toBeInTheDocument();
  expect(screen.getByText('抗阻训练')).toBeInTheDocument();
  expect(screen.getByText('被动助力训练')).toBeInTheDocument();
  expect(screen.getByText('--')).toBeInTheDocument();
});
