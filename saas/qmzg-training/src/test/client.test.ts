import { withAuthHeader } from '../api/client';
import { clearAccessToken, setAccessToken } from '../auth/session';

afterEach(clearAccessToken);

test('JWT request header is attached from sessionStorage', () => {
  setAccessToken('test-jwt');
  const config = withAuthHeader({ headers: { Accept: 'application/json' } });
  expect(config.headers).toMatchObject({
    Accept: 'application/json',
    Authorization: 'Bearer test-jwt',
  });
});
