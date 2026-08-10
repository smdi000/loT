import { Alert, Button, Empty, Spin } from 'antd';

interface Props {
  loading: boolean;
  error?: string | null;
  empty?: boolean;
  emptyText?: string;
  emptyHint?: string;
  emptyType?: 'default' | 'training' | 'device';
  onRetry?: () => void;
  children: React.ReactNode;
}

export default function AsyncState({ loading, error, empty, emptyText, emptyHint, emptyType = 'default', onRetry, children }: Props) {
  if (loading) {
    return (
      <div className="state-panel" role="status">
        <Spin size="large" />
        <span>正在同步训练云数据…</span>
      </div>
    );
  }
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="数据加载失败"
        description={error}
        action={onRetry ? <Button onClick={onRetry}>重新加载</Button> : undefined}
      />
    );
  }
  if (empty) {
    if (emptyType !== 'default') {
      return (
        <div className="visual-empty page-empty">
          <span className={emptyType === 'training' ? 'empty-training-icon' : 'empty-device-icon'} aria-hidden="true" />
          <strong>{emptyText || '暂无数据'}</strong>
          {emptyHint && <p>{emptyHint}</p>}
        </div>
      );
    }
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText || '暂无数据'} />;
  }
  return <>{children}</>;
}
