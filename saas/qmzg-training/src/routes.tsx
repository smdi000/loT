import { Redirect, Route, Switch } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuth } from './auth/AuthContext';
import AppShell from './components/AppShell';
import DashboardPage from './pages/DashboardPage';
import DevicesPage from './pages/DevicesPage';
import LoginPage from './pages/LoginPage';
import TrainingHistoryPage from './pages/TrainingHistoryPage';
import TrainingReportPage from './pages/TrainingReportPage';

function PrivateArea() {
  const { user, loading } = useAuth();
  if (loading) return <div className="fullscreen-state"><Spin size="large" /><span>正在验证安全会话…</span></div>;
  if (!user) return <Redirect to="/login" />;
  return <AppShell><Switch><Route exact path="/dashboard" component={DashboardPage} /><Route exact path="/devices" component={DevicesPage} /><Route exact path="/training" component={TrainingHistoryPage} /><Route exact path="/training/:id" component={TrainingReportPage} /><Redirect to="/dashboard" /></Switch></AppShell>;
}

export default function AppRoutes() {
  return <Switch><Route exact path="/login" component={LoginPage} /><Route path="/" component={PrivateArea} /></Switch>;
}
