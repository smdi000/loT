import { ConfigProvider } from 'antd';
import { IQiankunProps } from '.';
import { AuthProvider } from './auth/AuthContext';
import AppRoutes from './routes';
import './App.css';

function App(props: IQiankunProps) {
  return (
    <ConfigProvider getPopupContainer={() => props.container || document.body}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ConfigProvider>
  );
}

export default App;
