import { render, screen } from '@testing-library/react';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { MemoryRouter } from 'react-router-dom';
import * as services from '../api/services';
import DashboardPage from '../pages/DashboardPage';
import { testDevice, testSession } from './fixtures';

jest.mock('../api/services');
const mocked = services as jest.Mocked<typeof services>;

beforeEach(() => jest.clearAllMocks());

test('Dashboard displays the latest training-session average confidence', async () => {
  mocked.getDevices.mockResolvedValue([testDevice]);
  mocked.getAllTrainingSessions.mockResolvedValue([
    {
      ...testSession,
      avg_confidence: 9670,
      summary_json: { ...testSession.summary_json, action_confidence: 1234 },
    },
  ]);

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByText('最近训练平均置信度')).toBeInTheDocument();
  expect(screen.getAllByText('96.70%').length).toBeGreaterThan(0);
  expect(screen.getByText('二头弯举')).toBeInTheDocument();
  expect(screen.getByText('20')).toBeInTheDocument();
  expect(screen.getByText('设备 / 云端链路')).toBeInTheDocument();
  expect(screen.getByText('Intel Edge AI')).toBeInTheDocument();
  expect(screen.getByText('L610 · 4G')).toBeInTheDocument();
  expect(screen.getByText('Tuya IoT Cloud')).toBeInTheDocument();
  expect(screen.getByText('Alibaba Cloud')).toBeInTheDocument();
  expect(screen.queryByText('12.34%')).not.toBeInTheDocument();
  expect(mocked.getAllTrainingSessions).toHaveBeenCalledTimes(1);
});

test('Dashboard shows an empty confidence state instead of zero percent', async () => {
  mocked.getDevices.mockResolvedValue([]);
  mocked.getAllTrainingSessions.mockResolvedValue([]);

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByText('最近训练平均置信度')).toBeInTheDocument();
  expect(screen.getAllByText('--').length).toBeGreaterThan(0);
  expect(screen.getByText('暂无训练数据')).toBeInTheDocument();
  expect(screen.queryByText('0.00%')).not.toBeInTheDocument();
  expect(screen.queryByText('128.5°')).not.toBeInTheDocument();
});

test('Dashboard presentation mode keeps real data and exposes presentation layout', async () => {
  mocked.getDevices.mockResolvedValue([testDevice]);
  mocked.getAllTrainingSessions.mockResolvedValue([testSession]);

  const { container } = render(
    <MemoryRouter initialEntries={['/dashboard?presentation=1']}>
      <DashboardPage />
    </MemoryRouter>
  );

  expect((await screen.findAllByText('96.70%')).length).toBeGreaterThan(0);
  expect(container.querySelector('[data-presentation="true"]')).toBeInTheDocument();
  expect(screen.getByText('退出演示')).toBeInTheDocument();
  expect(screen.getByText('acceptance_cloud_training_001')).toBeInTheDocument();
});

test('Dashboard has no action-confidence dependency or polling loop', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/pages/DashboardPage.tsx'), 'utf8');
  expect(source).not.toContain('action_confidence');
  expect(source).not.toContain('setInterval');
  expect(source).not.toContain('setTimeout');
});
