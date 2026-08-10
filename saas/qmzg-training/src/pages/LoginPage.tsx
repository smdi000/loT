import { Alert, Button, Form, Input } from 'antd';
import { useState } from 'react';
import { Redirect, useHistory } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

interface LoginValues { email: string; password: string }

export default function LoginPage() {
  const history = useHistory();
  const { user, login } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Redirect to="/dashboard" />;

  const submit = async ({ email, password }: LoginValues) => {
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      history.replace('/dashboard');
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : '登录失败，请稍后重试';
      setError(message === 'invalid email or password' ? '账号或密码错误' : message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-visual">
        <div className="orb orb-one" /><div className="orb orb-two" />
        <div className="kinetic-figure" aria-hidden="true">
          <i className="joint joint-a" /><i className="joint joint-b" /><i className="joint joint-c" />
          <span className="limb limb-a" /><span className="limb limb-b" /><span className="limb limb-c" />
        </div>
        <div className="visual-copy">
          <span className="eyebrow">EDGE AI · CELLULAR IOT · CLOUD SAAS</span>
          <h1>让每一次训练<br />都有数据回响</h1>
          <p>外骨骼在边缘完成感知与分析，通过蜂窝网络将训练总结安全送达云端。</p>
          <div className="flow-tags"><span>边缘推理</span><b>→</b><span>4G 直连</span><b>→</b><span>云端分析</span></div>
        </div>
      </section>
      <section className="login-panel">
        <div className="login-card">
          <div className="login-logo"><div className="brand-mark"><span /></div><strong>擎梦智骨</strong></div>
          <span className="eyebrow">TRAINING INTELLIGENCE</span>
          <h2>擎梦智骨训练平台</h2>
          <p className="login-subtitle">边缘智能 · 蜂窝物联网 · 云端训练分析</p>
          {error && <Alert type="error" showIcon message={error} />}
          <Form layout="vertical" onFinish={submit} requiredMark={false}>
            <Form.Item label="账号" name="email" rules={[{ required: true, message: '请输入账号' }]}>
              <Input size="large" autoComplete="username" placeholder="name@example.com" aria-label="账号" />
            </Form.Item>
            <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password size="large" autoComplete="current-password" placeholder="请输入密码" aria-label="密码" />
            </Form.Item>
            <Button className="primary-action" type="primary" htmlType="submit" size="large" block loading={submitting}>
              进入训练平台
            </Button>
          </Form>
          <div className="security-note"><span>✓</span> JWT 会话仅保存在当前浏览器标签会话中</div>
        </div>
      </section>
    </main>
  );
}
