import './public-path';
import ReactDOM from 'react-dom';
import { BrowserRouter } from 'react-router-dom';
import { message } from 'antd';
import { CaptureContext, Event, Severity } from '@sentry/types';
import App from './App';
import './index.css';
import './styles/global.less';
import './styles/app.less';

export interface IQiankunProps {
  base: string;
  container: HTMLElement;
  dynamicProps: DynamicProps;
  getOwnMenu: () => { entry_name: string };
  hasPermission: (permissionCode: string) => boolean;
  isSupportMobile: boolean;
  mainHistory: mainHistory;
  modifySelectedMenu: () => void;
  region: 'tx' | 'us' | 'eu' | 'in' | 'ueaz' | 'we' | 'sea';
  resourcePrefix: string;
  sentry: {
    captureEvent: (event: Event) => string;
    captureMessage: (message: string, captureContext?: CaptureContext | Severity) => string;
    captureException: (exception: unknown, captureContext?: CaptureContext) => string;
  };
  tyLang: 'zh' | 'en';
  langResource: unknown;
}

export let microProps: IQiankunProps | undefined;

function render(props: IQiankunProps) {
  const { base, container } = props;
  const root = (
    container ? container.querySelector('#root') : document.querySelector('#root')
  ) as HTMLElement;
  message.config({ getContainer: () => root });
  ReactDOM.render(
    <BrowserRouter basename={window.__POWERED_BY_QIANKUN__ ? base || '/' : '/'}>
      <App {...props} />
    </BrowserRouter>,
    root
  );
}

if (!window.__POWERED_BY_QIANKUN__) {
  render({} as IQiankunProps);
}

export async function bootstrap() {
  // Required by the Tuya qiankun lifecycle.
}

export async function mount(props: IQiankunProps) {
  microProps = props;
  render(props);
}

export async function unmount(props: IQiankunProps) {
  const { container } = props;
  message.destroy();
  const root = (
    container ? container.querySelector('#root') : document.querySelector('#root')
  ) as HTMLElement;
  ReactDOM.unmountComponentAtNode(root);
}
