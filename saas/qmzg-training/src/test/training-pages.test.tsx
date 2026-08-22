import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route } from 'react-router-dom';
import * as services from '../api/services';
import TrainingHistoryPage from '../pages/TrainingHistoryPage';
import TrainingReportPage from '../pages/TrainingReportPage';
import { testDevice, testReport, testSession } from './fixtures';

jest.mock('../api/services');
const mocked = services as jest.Mocked<typeof services>;

beforeEach(() => jest.clearAllMocks());

test('training history renders an accepted real session', async () => {
  mocked.getTrainingSessions.mockResolvedValue({ items: [testSession], page: 1, page_size: 10, total: 1 });
  mocked.getDevices.mockResolvedValue([testDevice]);
  render(<MemoryRouter><TrainingHistoryPage /></MemoryRouter>);
  expect(await screen.findByText('57 次')).toBeInTheDocument();
  expect(screen.getByText('96.70%')).toBeInTheDocument();
  expect(screen.getByText('主动助力训练')).toBeInTheDocument();
  expect(screen.getByTitle('acceptance_cloud_training_001')).toBeInTheDocument();
  expect(screen.getByText('查看报告 →')).toBeInTheDocument();
});

test('training history renders an empty state', async () => {
  mocked.getTrainingSessions.mockResolvedValue({ items: [], page: 1, page_size: 10, total: 0 });
  mocked.getDevices.mockResolvedValue([]);
  render(<MemoryRouter><TrainingHistoryPage /></MemoryRouter>);
  expect(await screen.findByText('暂无训练记录')).toBeInTheDocument();
});

test('training history renders API errors without a white screen', async () => {
  mocked.getTrainingSessions.mockRejectedValue(new Error('训练云暂时不可用'));
  mocked.getDevices.mockResolvedValue([]);
  render(<MemoryRouter><TrainingHistoryPage /></MemoryRouter>);
  expect(await screen.findByText('训练云暂时不可用')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '重新加载' })).toBeInTheDocument();
});

test('training report renders the real acceptance values and non-medical notice', async () => {
  mocked.getTrainingSession.mockResolvedValue(testSession);
  mocked.getTrainingReport.mockResolvedValue(testReport);
  render(
    <MemoryRouter initialEntries={['/training/session-1']}>
      <Route path="/training/:id"><TrainingReportPage /></Route>
    </MemoryRouter>
  );
  await waitFor(() => expect(screen.getByTitle('acceptance_cloud_training_001')).toBeInTheDocument());
  expect(screen.getByText('10 分 23 秒')).toBeInTheDocument();
  expect(screen.getAllByText('57').length).toBeGreaterThan(0);
  expect(screen.getAllByText('96.70%').length).toBeGreaterThan(0);
  expect(screen.getAllByText('128.5°').length).toBeGreaterThan(0);
  expect(screen.getAllByText('93.4°').length).toBeGreaterThan(0);
  expect(screen.getByText('二头弯举')).toBeInTheDocument();
  expect(screen.getByText('抬臂')).toBeInTheDocument();
  expect(screen.getByText('侧平举')).toBeInTheDocument();
  expect(screen.getByText('拳击')).toBeInTheDocument();
  expect(screen.getByText('0')).toBeInTheDocument();
  expect(screen.getByText(/不构成医疗诊断或治疗建议/)).toBeInTheDocument();
  expect(screen.queryByText(/正常参考范围/)).not.toBeInTheDocument();
  expect(screen.getAllByText('主动助力训练').length).toBeGreaterThan(0);
  expect(screen.queryByText('演示数据')).not.toBeInTheDocument();
});

test('training report marks mock provenance without changing its training type', async () => {
  mocked.getTrainingSession.mockResolvedValue({ ...testSession, source_type: 'mock', training_type: 'resistance' });
  mocked.getTrainingReport.mockResolvedValue({ ...testReport, training_type: 'resistance' });
  render(
    <MemoryRouter initialEntries={['/training/session-1']}>
      <Route path="/training/:id"><TrainingReportPage /></Route>
    </MemoryRouter>
  );
  expect((await screen.findAllByText('演示数据')).length).toBeGreaterThan(0);
  expect(screen.getAllByText('抗阻训练').length).toBeGreaterThan(0);
});

test('training history uses a neutral marker for a historical null training type', async () => {
  mocked.getTrainingSessions.mockResolvedValue({ items: [{ ...testSession, training_type: null }], page: 1, page_size: 10, total: 1 });
  mocked.getDevices.mockResolvedValue([testDevice]);
  render(<MemoryRouter><TrainingHistoryPage /></MemoryRouter>);
  expect(await screen.findByText('--')).toBeInTheDocument();
});
