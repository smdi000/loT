import { Button, Card } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getAllTrainingSessions, getDevices } from '../api/services';
import { Device, TrainingAction, TrainingSession } from '../api/types';
import ActionDistribution from '../components/ActionDistribution';
import AsyncState from '../components/AsyncState';
import { summarizeSessions } from '../utils/dashboard';
import { formatConfidence, formatDate, formatDuration, maskDeviceId } from '../utils/format';

function readActions(session: TrainingSession | null): TrainingAction[] {
  const actions = session?.summary_json?.actions;
  if (!actions || typeof actions !== 'object' || Array.isArray(actions)) return [];
  return Object.entries(actions)
    .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && entry[1] >= 0)
    .map(([name, count]) => ({ name, count }));
}

function formatClock(seconds?: number | null) {
  if (seconds === null || seconds === undefined) return '--';
  const minutes = Math.floor(seconds / 60);
  const rest = Math.max(0, seconds % 60);
  return `${minutes}:${String(rest).padStart(2, '0')}`;
}

export default function DashboardPage() {
  const location = useLocation();
  const [devices, setDevices] = useState<Device[]>([]);
  const [sessions, setSessions] = useState<TrainingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const presentation = new URLSearchParams(location.search).get('presentation') === '1';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextDevices, nextSessions] = await Promise.all([getDevices(), getAllTrainingSessions()]);
      setDevices(nextDevices);
      setSessions(nextSessions);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法加载训练总览');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  const summary = summarizeSessions(sessions);
  const latest = summary.latest;
  const actions = useMemo(() => readActions(latest), [latest]);

  return (
    <div className={`page dashboard-page${presentation ? ' dashboard-presentation' : ''}`} data-presentation={presentation ? 'true' : 'false'}>
      <section className="dashboard-hero">
        <div className="hero-copy">
          <span className="eyebrow">TRAINING INTELLIGENCE</span>
          <h1>训练数据中心</h1>
          <p>边缘 AI 驱动的训练数据，通过蜂窝网络连接云端。</p>
        </div>
        <div className="capability-badges" aria-label="产品技术链路">
          <span><i />EDGE AI</span>
          <span><i />4G CELLULAR</span>
          <span><i />CLOUD SaaS</span>
        </div>
        <div className="hero-actions">
          {!presentation && <Link className="presentation-link" to="/dashboard?presentation=1">演示模式</Link>}
          {presentation && <Link className="presentation-link" to="/dashboard">退出演示</Link>}
          <Button onClick={load}>刷新数据</Button>
        </div>
      </section>

      <AsyncState loading={loading} error={error} onRetry={load}>
        <section className="overview-strip" aria-label="训练总览指标">
          <div><strong>{devices.length}</strong><span>已绑定设备</span></div>
          <div><strong>{summary.trainingCount}</strong><span>累计训练</span></div>
          <div><strong>{summary.totalReps}</strong><span>累计动作</span></div>
          <div><strong>{summary.totalDuration ? formatDuration(summary.totalDuration) : '--'}</strong><span>累计训练时长</span></div>
        </section>

        <section className="dashboard-primary-grid">
          <Card className="panel-card latest-training-card" bordered={false}>
            <div className="card-title">
              <div><span className="eyebrow">LATEST TRAINING</span><h2>最近一次训练</h2></div>
              {latest && <Link to={`/training/${latest.id}`}>查看完整报告 →</Link>}
            </div>
            {latest ? (
              <div className="latest-training-content">
                <div className="confidence-gauge" style={{ ['--score' as string]: `${(latest.avg_confidence || 0) / 100}%` }}>
                  <div className="confidence-gauge-inner">
                    <small>SESSION AVERAGE</small>
                    <strong>{formatConfidence(latest.avg_confidence)}</strong>
                    <span>最近训练平均置信度</span>
                  </div>
                </div>
                <div className="latest-training-copy">
                  <div className="session-meta"><span>{formatDate(latest.started_at)}</span><code>{latest.external_session_id}</code></div>
                  <div className="latest-metrics">
                    <div><strong>{formatClock(latest.duration_sec)}</strong><span>训练时长</span></div>
                    <div><strong>{latest.total_reps ?? '--'}</strong><span>动作次数</span></div>
                    <div><strong>{latest.max_elbow_angle === null ? '--' : `${(latest.max_elbow_angle / 10).toFixed(1)}°`}</strong><span>最大肘角</span></div>
                    <div><strong>{latest.max_shoulder_angle === null ? '--' : `${(latest.max_shoulder_angle / 10).toFixed(1)}°`}</strong><span>最大肩角</span></div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="visual-empty latest-empty">
                <span className="empty-training-icon" aria-hidden="true" />
                <strong>暂无训练数据</strong>
                <p>完成一次训练后，这里会显示训练摘要。</p>
                <div className="empty-confidence"><span>最近训练平均置信度</span><strong>--</strong></div>
              </div>
            )}
          </Card>

          <Card className="panel-card pipeline-card" bordered={false}>
            <div className="card-title"><div><span className="eyebrow">DEVICE PIPELINE</span><h2>设备 / 云端链路</h2></div></div>
            <div className="pipeline-device">
              <div className="pipeline-device-mark">EXO<small>L610</small></div>
              <div><strong>{devices[0]?.display_name || '外骨骼训练设备'}</strong><span>{devices[0] ? maskDeviceId(devices[0].id) : '尚未绑定设备'}</span></div>
            </div>
            <div className="pipeline-flow" aria-label="Intel Edge AI 到 Alibaba Cloud 的数据链路">
              <div><i className="pipeline-node" /><span>Intel Edge AI</span><small>边缘识别</small></div>
              <b aria-hidden="true" />
              <div><i className="pipeline-node" /><span>L610 · 4G</span><small>蜂窝通信</small></div>
              <b aria-hidden="true" />
              <div><i className="pipeline-node" /><span>Tuya IoT Cloud</span><small>设备云</small></div>
              <b aria-hidden="true" />
              <div><i className="pipeline-node" /><span>Alibaba Cloud</span><small>训练业务云</small></div>
            </div>
            <div className="last-sync"><span>LAST DATA SYNC</span><strong>{latest ? formatDate(latest.created_at) : '--'}</strong></div>
          </Card>
        </section>

        <section className="dashboard-secondary-grid">
          <Card className="panel-card action-card" bordered={false}>
            <div className="card-title"><div><span className="eyebrow">ACTION DISTRIBUTION</span><h2>动作分布</h2></div>{latest && <span>本次共 {latest.total_reps} 次</span>}</div>
            <ActionDistribution actions={actions} compact />
          </Card>

          <Card className="panel-card recent-sessions-card" bordered={false}>
            <div className="card-title"><div><span className="eyebrow">RECENT SESSIONS</span><h2>最近训练</h2></div><Link to="/training">全部记录 →</Link></div>
            {summary.recent.length ? (
              <div className="recent-session-list">
                {summary.recent.map(item => (
                  <Link className="recent-session-row" to={`/training/${item.id}`} key={item.id}>
                    <time>{formatDate(item.started_at)}</time>
                    <span><strong>{formatDuration(item.duration_sec)}</strong><small>训练时长</small></span>
                    <span><strong>{item.total_reps ?? '--'} 次</strong><small>动作次数</small></span>
                    <span><strong>{formatConfidence(item.avg_confidence)}</strong><small>平均置信度</small></span>
                    <i>→</i>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="visual-empty compact-empty"><span className="empty-training-icon" aria-hidden="true" /><strong>暂无训练记录</strong><p>完成一次训练后，这里会显示训练摘要。</p></div>
            )}
          </Card>
        </section>
      </AsyncState>
    </div>
  );
}
