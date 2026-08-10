import { Button, Card, Tag } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getTrainingReport, getTrainingSession } from '../api/services';
import { TrainingReport, TrainingSession } from '../api/types';
import ActionDistribution from '../components/ActionDistribution';
import AsyncState from '../components/AsyncState';
import JointAngleVisual from '../components/JointAngleVisual';
import { formatDate, formatDuration, maskDeviceId } from '../utils/format';

function softenSessionId(value: string) {
  if (value.length <= 26) return value;
  return `${value.slice(0, 15)}…${value.slice(-8)}`;
}

export default function TrainingReportPage() {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<TrainingSession | null>(null);
  const [report, setReport] = useState<TrainingReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSession, nextReport] = await Promise.all([getTrainingSession(id), getTrainingReport(id)]);
      setSession(nextSession);
      setReport(nextReport);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法加载训练报告');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="page report-page">
      <div className="page-heading report-heading">
        <div><span className="eyebrow">TRAINING REPORT</span><h1>训练报告</h1><p>运动训练数据总结</p></div>
        <Link to="/training"><Button>← 返回训练记录</Button></Link>
      </div>
      <AsyncState loading={loading} error={error} onRetry={load}>
        {report && session && (
          <>
            <section className="report-hero">
              <div className="report-hero-copy">
                <Tag color="cyan">TRAINING COMPLETE</Tag>
                <h2>{formatDate(session.started_at)}</h2>
                <p><span>{maskDeviceId(session.device_id)}</span><code title={session.external_session_id}>{softenSessionId(session.external_session_id)}</code></p>
              </div>
              <div className="report-confidence">
                <span>AVERAGE CONFIDENCE</span>
                <strong>{report.avg_confidence.toFixed(2)}%</strong>
                <small>本次训练平均动作识别置信度</small>
              </div>
            </section>

            <section className="report-key-metrics" aria-label="训练核心指标">
              <div><span>TOTAL REPS</span><strong>{report.total_reps}</strong><small>动作总数 / 次</small></div>
              <div><span>AVG CONFIDENCE</span><strong>{report.avg_confidence.toFixed(2)}%</strong><small>平均置信度</small></div>
              <div><span>MAX ELBOW</span><strong>{report.range_of_motion.elbow_max.toFixed(1)}°</strong><small>最大肘关节角度</small></div>
              <div><span>MAX SHOULDER</span><strong>{report.range_of_motion.shoulder_max.toFixed(1)}°</strong><small>最大肩关节角度</small></div>
            </section>

            <section className="report-content-grid">
              <Card className="panel-card report-actions-card" bordered={false}>
                <div className="card-title"><div><span className="eyebrow">ACTION DISTRIBUTION</span><h2>动作分布</h2></div><span>共 {report.total_reps} 次</span></div>
                <ActionDistribution actions={report.actions} />
              </Card>

              <Card className="panel-card joint-range-card" bordered={false}>
                <div className="card-title"><div><span className="eyebrow">JOINT RANGE</span><h2>关节最大活动角度</h2></div></div>
                <p className="joint-range-note">仅表示本次训练记录到的最大角度。</p>
                <div className="joint-range-grid">
                  <JointAngleVisual code="ELBOW" label="肘关节" value={report.range_of_motion.elbow_max} />
                  <JointAngleVisual code="SHOULDER" label="肩关节" value={report.range_of_motion.shoulder_max} tone="violet" />
                </div>
              </Card>
            </section>

            <Card className="panel-card report-summary-card" bordered={false}>
              <div className="card-title"><div><span className="eyebrow">TRAINING SUMMARY</span><h2>训练摘要</h2></div></div>
              <div className="summary-grid">
                <div><span>训练时长</span><strong>{formatDuration(report.duration_sec)}</strong></div>
                <div><span>动作类型</span><strong>{report.actions.length} 类</strong></div>
                <div><span>设备异常数量</span><strong>{report.fault_count ?? 0}</strong></div>
                <div><span>数据来源</span><strong>Tuya Property</strong></div>
              </div>
              <div className="report-notice">训练数据分析仅用于运动训练信息展示，不构成医疗诊断或治疗建议。</div>
            </Card>
          </>
        )}
      </AsyncState>
    </div>
  );
}
