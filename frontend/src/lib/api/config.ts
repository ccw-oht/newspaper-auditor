const DEFAULT_BASE_URL = 'http://localhost:8000';

let apiBase = DEFAULT_BASE_URL;

interface AppConfigWindow {
  __APP_CONFIG__?: {
    apiBaseUrl?: string;
  };
}

if (typeof window !== 'undefined') {
  const exposed = (window as unknown as AppConfigWindow).__APP_CONFIG__?.apiBaseUrl;
  if (typeof exposed === 'string' && exposed.trim().length > 0) {
    apiBase = exposed;
  }
}

export const API_BASE_URL = apiBase.replace(/\/$/, '');
