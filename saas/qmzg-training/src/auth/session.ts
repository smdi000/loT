const TOKEN_KEY = 'qmzg.training.access_token';

export function getAccessToken(): string | null {
  return window.sessionStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  window.sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  window.sessionStorage.removeItem(TOKEN_KEY);
}

export { TOKEN_KEY };
