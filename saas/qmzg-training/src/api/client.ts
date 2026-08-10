import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { clearAccessToken, getAccessToken } from '../auth/session';
import { FastApiError } from './types';

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function withAuthHeader(config: AxiosRequestConfig): AxiosRequestConfig {
  const token = getAccessToken();
  return {
    ...config,
    headers: {
      ...config.headers,
      'Content-Type': 'application/json;charset=utf-8',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };
}

function errorMessage(error: AxiosError<FastApiError>): string {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(item => item.msg).filter(Boolean);
    if (messages.length) return messages.join('；');
  }
  if (!error.response) return '无法连接训练云，请检查网络后重试';
  return `请求失败（${error.response.status}）`;
}

const api = axios.create({ baseURL: '/custom-api', timeout: 12000 });
api.interceptors.request.use(withAuthHeader);
api.interceptors.response.use(
  response => response,
  (error: AxiosError<FastApiError>) => {
    const status = error.response?.status;
    if (status === 401) {
      clearAccessToken();
      window.dispatchEvent(new Event('qmzg:auth-expired'));
    }
    return Promise.reject(new ApiError(errorMessage(error), status));
  }
);

export default api;
