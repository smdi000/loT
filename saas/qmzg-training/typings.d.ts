declare module '*.css';
declare module '*.module.less';
declare module '*.sass';
declare module '*.png';
declare module '*.jpg';
declare module '*.jpeg';
declare module '*.gif';
declare module '*.webp';
declare module '*.svg' {
  export function ReactComponent(props: React.SVGProps<SVGSVGElement>): React.ReactElement;
  const url: string;
  export default url;
}
interface Window {
  __POWERED_BY_QIANKUN__: string;
}


interface DynamicProps {
  setBreadcrumb: SetBreadcrumb;
  [key: string]: any;
}

interface SetBreadcrumb {
  (breadcrumbInfos?: BreadcrumbInfoInput[]): void;
}

type BreadcrumbInfoInput =
  | {
      type: 'auto' | 'root';
      name?: never;
      path?: never;
    }
  | {
      type: 'menu';
      name?: never;
      path: string;
    }
  | {
      type: 'c';
      name: string;
      path: string;
    };

interface mainHistory {
  push: (path, state?) => void;
  replace: (path, state?) => void;
  go: (n: number) => void;
  goBack: () => void;
  goForward: () => void;
}