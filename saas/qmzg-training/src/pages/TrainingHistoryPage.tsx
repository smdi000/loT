import { Card, Select, Table, Tag } from 'antd';
import { ColumnsType } from 'antd/lib/table';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getDevices, getTrainingSessions } from '../api/services';
import { Device, TrainingSession, TrainingSessionPage } from '../api/types';
import AsyncState from '../components/AsyncState';
import { formatConfidence, formatDate, formatDuration, maskDeviceId } from '../utils/format';

const emptyPage: TrainingSessionPage = { items: [], page: 1, page_size: 10, total: 0 };

function softenSessionId(value: string) {
  if (value.length <= 24) return value;
  return `${value.slice(0, 12)}…${value.slice(-7)}`;
}

export default function TrainingHistoryPage() {
  const [data, setData] = useState(emptyPage);
  const [devices, setDevices] = useState<Device[]>([]);
  const [page, setPage] = useState(1);
  const [deviceId, setDeviceId] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [sessions, nextDevices] = await Promise.all([getTrainingSessions(page, 10, deviceId), getDevices()]);
      setData(sessions); setDevices(nextDevices);
    } catch (reason) { setError(reason instanceof Error ? reason.message : '无法加载训练历史'); }
    finally { setLoading(false); }
  }, [page, deviceId]);

  useEffect(() => { load(); }, [load]);

  const columns: ColumnsType<TrainingSession> = [
    { title: '训练时间', dataIndex: 'started_at', render: (value, row) => <div className="time-cell"><strong>{formatDate(value)}</strong><span>训练完成</span><code title={row.external_session_id}>{softenSessionId(row.external_session_id)}</code></div> },
    { title: '训练时长', dataIndex: 'duration_sec', render: value => formatDuration(value) },
    { title: '动作次数', dataIndex: 'total_reps', render: value => `${value || 0} 次` },
    { title: '平均置信度', dataIndex: 'avg_confidence', render: value => <Tag color="cyan">{formatConfidence(value)}</Tag> },
    { title: '设备', dataIndex: 'device_id', render: value => maskDeviceId(value) },
    { title: '', key: 'detail', render: (_, row) => <Link className="table-action" to={`/training/${row.id}`}>查看报告 →</Link> },
  ];

  return (
    <div className="page training-page">
      <div className="page-heading"><div><span className="eyebrow">TRAINING ARCHIVE</span><h1>训练历史</h1><p>按时间倒序查看已归档的真实训练会话。</p></div><Select allowClear value={deviceId} placeholder="全部设备" onChange={value => { setDeviceId(value); setPage(1); }} style={{ minWidth: 210 }} options={devices.map(device => ({ value: device.id, label: maskDeviceId(device.id) }))} /></div>
      <Card className="panel-card table-card" bordered={false}>
        <AsyncState loading={loading} error={error} empty={!data.items.length} emptyText="暂无训练记录" emptyHint="完成一次训练后，这里会显示训练摘要。" emptyType="training" onRetry={load}>
          <Table rowKey="id" columns={columns} dataSource={data.items} pagination={{ current: data.page, pageSize: data.page_size, total: data.total, showSizeChanger: false, onChange: setPage, showTotal: total => `共 ${total} 次训练` }} />
        </AsyncState>
      </Card>
    </div>
  );
}
