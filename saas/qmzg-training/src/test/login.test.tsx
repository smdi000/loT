import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import { ApiError } from '../api/client';

const loginMock = jest.fn();

jest.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false, login: loginMock, logout: jest.fn() }),
}));

beforeEach(() => loginMock.mockReset());

function renderLogin() {
  return render(<MemoryRouter initialEntries={['/login']}><LoginPage /></MemoryRouter>);
}

test('login success submits credentials through the auth layer', async () => {
  loginMock.mockResolvedValue(undefined);
  renderLogin();
  fireEvent.change(screen.getByLabelText('账号'), { target: { value: 'demo@example.test' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'safe-password' } });
  fireEvent.click(screen.getByRole('button', { name: '进入训练平台' }));
  await waitFor(() => expect(loginMock).toHaveBeenCalledWith('demo@example.test', 'safe-password'));
});

test('login failure shows a friendly authentication error', async () => {
  loginMock.mockRejectedValue(new ApiError('invalid email or password', 401));
  renderLogin();
  fireEvent.change(screen.getByLabelText('账号'), { target: { value: 'demo@example.test' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'wrong-password' } });
  fireEvent.click(screen.getByRole('button', { name: '进入训练平台' }));
  expect(await screen.findByText('账号或密码错误')).toBeInTheDocument();
});
