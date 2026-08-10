import { Avatar, Button, Layout } from 'antd';
import { Link, useHistory, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import { microProps } from '../index';

const { Header, Content } = Layout;

const navItems = [
  { path: '/dashboard', label: '总览', glyph: '◫' },
  { path: '/devices', label: '我的设备', glyph: '⌁' },
  { path: '/training', label: '训练记录', glyph: '↗' },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const history = useHistory();
  const { user, logout } = useAuth();
  const selected = navItems.find(item => location.pathname.startsWith(item.path))?.path || '/dashboard';
  const presentation = location.pathname === '/dashboard' && new URLSearchParams(location.search).get('presentation') === '1';

  useEffect(() => {
    microProps?.dynamicProps?.setBreadcrumb?.([{ type: 'auto' }]);
  }, [location.pathname]);

  const signOut = () => {
    logout();
    history.replace('/login');
  };

  return (
    <Layout className={`app-shell${presentation ? ' presentation-mode' : ''}`}>
      <Header className="topbar">
        <div className="topbar-inner">
          <Link className="brand-block" to="/dashboard" aria-label="擎梦智骨训练平台首页">
          <div className="brand-mark"><span /></div>
          <div>
            <strong>擎梦智骨</strong>
            <span>TRAINING INTELLIGENCE</span>
          </div>
          </Link>
          <nav className="main-nav" aria-label="主导航">
          {navItems.map(item => (
              <Link className={selected === item.path ? 'active' : ''} key={item.path} to={item.path}>
                <span className="nav-glyph">{item.glyph}</span>{item.label}
              </Link>
          ))}
          </nav>
          <div className="user-area">
            <Avatar>{(user?.display_name || user?.email || 'U').slice(0, 1).toUpperCase()}</Avatar>
            <div className="user-copy"><strong>{user?.display_name || '训练用户'}</strong><span>{user?.email}</span></div>
            <Button type="text" onClick={signOut}>退出</Button>
          </div>
        </div>
      </Header>
      <Content className="app-content">{children}</Content>
    </Layout>
  );
}
