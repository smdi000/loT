import { TrainingAction } from '../api/types';

const actionNames: Record<string, { zh: string; en: string }> = {
  curl: { zh: '二头弯举', en: 'CURL' },
  raise: { zh: '抬臂', en: 'RAISE' },
  lateral: { zh: '侧平举', en: 'LATERAL' },
  boxing: { zh: '拳击', en: 'BOXING' },
};

interface Props {
  actions: TrainingAction[];
  compact?: boolean;
}

export default function ActionDistribution({ actions, compact = false }: Props) {
  const maxCount = Math.max(1, ...actions.map(action => action.count));
  const total = actions.reduce((sum, action) => sum + action.count, 0);

  if (!actions.length) {
    return (
      <div className="visual-empty compact-empty">
        <span className="empty-training-icon" aria-hidden="true" />
        <strong>暂无动作统计</strong>
        <p>完成一次训练后，这里会显示训练摘要。</p>
      </div>
    );
  }

  return (
    <div className={`action-distribution${compact ? ' action-distribution-compact' : ''}`}>
      {actions.map((action, index) => {
        const label = actionNames[action.name] || { zh: action.name, en: action.name.toUpperCase() };
        const percentage = total ? Math.round((action.count / total) * 100) : 0;
        return (
          <div className="action-row" key={action.name}>
            <div className="action-label">
              <span>{label.zh}</span>
              <small>{label.en}</small>
            </div>
            <div className="action-track" aria-label={`${label.zh} ${action.count} 次，占 ${percentage}%`}>
              <i style={{ width: `${(action.count / maxCount) * 100}%`, animationDelay: `${index * 70}ms` }} />
            </div>
            <strong>{action.count}</strong>
            <small className="action-percentage">{percentage}%</small>
          </div>
        );
      })}
    </div>
  );
}
