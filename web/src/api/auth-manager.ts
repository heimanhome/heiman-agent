import { authApi } from './client';

export interface AuthToken {
  access_token: string;
  refresh_token: string;
  expires_at: string;
  token_type: string;
  scope?: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  token: AuthToken | null;
  profile: UserProfile | null;
  loading: boolean;
}

export interface UserProfile {
  username: string;
  email: string;
  phone: string;
  bindStatus: boolean;
  userId?: string;
}

const STORAGE_KEYS = {
  TOKEN: 'heiman_auth_token',
  PROFILE: 'heiman_user_profile',
  REMEMBER_ME: 'heiman_remember_me',
  TOKEN_SOURCE: 'heiman_token_source',
};

const STORAGE_VERSION = '1.0';

export class AuthManager {
  private static instance: AuthManager;
  private token: AuthToken | null = null;
  private profile: UserProfile | null = null;
  private refreshTimer: ReturnType<typeof setTimeout> | null = null;
  private onTokenChangeCallbacks: Array<(token: AuthToken | null) => void> = [];

  private constructor() {
    this.loadFromStorage();
    this.startTokenRefreshMonitor();
  }

  public static getInstance(): AuthManager {
    if (!AuthManager.instance) {
      AuthManager.instance = new AuthManager();
    }
    return AuthManager.instance;
  }

  public getToken(): AuthToken | null {
    return this.token;
  }

  public getAccessToken(): string | null {
    return this.token?.access_token || null;
  }

  public getProfile(): UserProfile | null {
    return this.profile;
  }

  public isAuthenticated(): boolean {
    if (!this.token) return false;
    return !this.isTokenExpired(this.token);
  }

  public isTokenExpired(token: AuthToken): boolean {
    try {
      const expires = new Date(token.expires_at);
      const now = new Date();
      const threshold = 60 * 1000;
      return expires.getTime() - now.getTime() < threshold;
    } catch {
      return true;
    }
  }

  public async login(username: string, password: string, rememberMe: boolean = false): Promise<AuthState> {
    try {
      const response = await authApi.login(username, password, rememberMe);
      
      if (response.success && response.data) {
        const token: AuthToken = {
          access_token: response.data.access_token,
          refresh_token: response.data.refresh_token,
          expires_at: this.normalizeExpiresAt(response.data.expires_at, response.data.expires_in),
          token_type: 'Bearer',
        };

        this.token = token;
        await this.saveToStorage(rememberMe);
        
        await this.fetchProfile();
        this.startTokenRefreshMonitor();
        
        this.notifyTokenChange(token);
        return { isAuthenticated: true, token, profile: this.profile, loading: false };
      }
      
      return { isAuthenticated: false, token: null, profile: null, loading: false };
    } catch (error) {
      this.clearAuth();
      throw error;
    }
  }

  public async refreshToken(): Promise<AuthToken | null> {
    if (!this.token?.refresh_token) {
      this.clearAuth();
      return null;
    }

    try {
      const response = await authApi.refreshToken();

      if (response.success && response.data) {
        // authApi.refreshToken() 内部已调用 setToken() 更新了 this.token
        const newToken = this.token;
        if (newToken) {
          this.notifyTokenChange(newToken);
          return newToken;
        }
      }

      // refresh 接口明确返回失败(401/400),清除认证
      this.clearAuth();
      return null;
    } catch (error: unknown) {
      // 仅在 401/400 时清除 token,其他错误(如 500/网络超时)保留现有认证状态
      const status = (error as { status?: number; response?: { status?: number } })?.response?.status
        ?? (error as { status?: number })?.status;
      if (status === 401 || status === 400) {
        this.clearAuth();
      } else {
        console.warn('[AuthManager] Token refresh failed (non-auth error), keeping existing token:', error);
      }
      return null;
    }
  }

  public async logout(): Promise<void> {
    this.clearAuth();
    window.location.href = '/auth/login';
  }

  public async fetchProfile(): Promise<UserProfile | null> {
    try {
      const response = await authApi.getProfile();
      
      if (response.data?.success && response.data.data) {
        this.profile = response.data.data;
        await this.saveProfileToStorage();
        return this.profile;
      }
      
      return null;
    } catch {
      return null;
    }
  }

  public isRememberMe(): boolean {
    return localStorage.getItem(STORAGE_KEYS.REMEMBER_ME) === 'true';
  }

  public setToken(token: AuthToken): void {
    this.token = token;
    this.saveToStorage(this.isRememberMe());
    this.startTokenRefreshMonitor();
    this.notifyTokenChange(token);
  }

  public onTokenChange(callback: (token: AuthToken | null) => void): () => void {
    this.onTokenChangeCallbacks.push(callback);
    
    return () => {
      const index = this.onTokenChangeCallbacks.indexOf(callback);
      if (index > -1) {
        this.onTokenChangeCallbacks.splice(index, 1);
      }
    };
  }

  private notifyTokenChange(token: AuthToken | null): void {
    this.onTokenChangeCallbacks.forEach(callback => {
      try {
        callback(token);
      } catch (error) {
        console.error('Token change callback error:', error);
      }
    });
  }

  private calculateExpiresAt(expiresIn?: number): string {
    if (!expiresIn) {
      const future = new Date();
      future.setHours(future.getHours() + 24);
      return future.toISOString();
    }

    const expires = new Date();
    expires.setSeconds(expires.getSeconds() + expiresIn);
    return expires.toISOString();
  }

  private normalizeExpiresAt(expiresAt: unknown, expiresIn?: number): string {
    if (!expiresAt) {
      return this.calculateExpiresAt(expiresIn);
    }

    if (typeof expiresAt === 'number') {
      const seconds = expiresAt > 1e12 ? expiresAt / 1000 : expiresAt;
      return new Date(seconds * 1000).toISOString();
    }

    if (typeof expiresAt === 'string') {
      const parsed = new Date(expiresAt);
      if (!Number.isNaN(parsed.getTime())) {
        return parsed.toISOString();
      }
      const asNumber = Number(expiresAt);
      if (!Number.isNaN(asNumber)) {
        const seconds = asNumber > 1e12 ? asNumber / 1000 : asNumber;
        return new Date(seconds * 1000).toISOString();
      }
    }

    return this.calculateExpiresAt(expiresIn);
  }

  private async saveToStorage(rememberMe: boolean): Promise<void> {
    if (!this.token) return;

    const storage = rememberMe ? localStorage : sessionStorage;
    
    const tokenData = {
      ...this.token,
      version: STORAGE_VERSION,
      savedAt: new Date().toISOString(),
      hash: this.generateHash(this.token.access_token),
    };

    try {
      storage.setItem(STORAGE_KEYS.TOKEN, JSON.stringify(tokenData));
      
      if (rememberMe) {
        localStorage.setItem(STORAGE_KEYS.REMEMBER_ME, 'true');
        sessionStorage.removeItem(STORAGE_KEYS.REMEMBER_ME);
      } else {
        sessionStorage.setItem(STORAGE_KEYS.REMEMBER_ME, 'false');
        localStorage.removeItem(STORAGE_KEYS.REMEMBER_ME);
      }
    } catch (error) {
      console.error('Failed to save token to storage:', error);
    }
  }

  private async saveProfileToStorage(): Promise<void> {
    if (!this.profile) return;

    const storage = this.isRememberMe() ? localStorage : sessionStorage;
    
    try {
      storage.setItem(STORAGE_KEYS.PROFILE, JSON.stringify(this.profile));
    } catch (error) {
      console.error('Failed to save profile to storage:', error);
    }
  }

  private loadFromStorage(): void {
    try {
      const rememberMe = localStorage.getItem(STORAGE_KEYS.REMEMBER_ME) === 'true';
      const storage = rememberMe ? localStorage : sessionStorage;
      
      const tokenDataStr = storage.getItem(STORAGE_KEYS.TOKEN);
      if (tokenDataStr) {
        const tokenData = JSON.parse(tokenDataStr);
        
        if (this.validateTokenData(tokenData)) {
          this.token = {
            access_token: tokenData.access_token,
            refresh_token: tokenData.refresh_token,
            expires_at: tokenData.expires_at,
            token_type: tokenData.token_type,
            scope: tokenData.scope,
          };
          
          if (!this.isTokenExpired(this.token)) {
            const profileStr = storage.getItem(STORAGE_KEYS.PROFILE);
            if (profileStr) {
              this.profile = JSON.parse(profileStr);
            }
          }
        }
      }

      if (!this.token) {
        const oauthToken = localStorage.getItem('heiman_access_token');
        const oauthRefreshToken = localStorage.getItem('heiman_refresh_token');
        const oauthExpires = localStorage.getItem('heiman_token_expires');
        
        if (oauthToken && oauthExpires) {
          this.token = {
            access_token: oauthToken,
            refresh_token: oauthRefreshToken || '',
            expires_at: oauthExpires,
            token_type: 'Bearer',
          };
          
          console.log('[AuthManager] Loaded token from OAuth login:', oauthToken.slice(0, 20) + '...');
        }
      }

      const serverToken = (window as unknown as { __HEIMAN_TOKEN__?: string }).__HEIMAN_TOKEN__;
      if (serverToken && serverToken !== '__HEIMAN_INJECT_TOKEN_HERE__') {
        if (!this.token || this.token.access_token !== serverToken) {
          this.token = {
            access_token: serverToken,
            refresh_token: '',
            expires_at: this.calculateExpiresAt(7200),
            token_type: 'Bearer',
          };
          
          localStorage.setItem(STORAGE_KEYS.TOKEN_SOURCE, 'server_injected');
          console.log('Token injected from server:', serverToken);
        }
      }
    } catch (error) {
      console.error('Failed to load auth data from storage:', error);
      this.clearAuth();
    }
  }

  private validateTokenData(tokenData: unknown): boolean {
    if (typeof tokenData !== 'object' || !tokenData) return false;
    
    const data = tokenData as Record<string, unknown>;
    
    if (!data.access_token || typeof data.access_token !== 'string') return false;
    if (!data.refresh_token || typeof data.refresh_token !== 'string') return false;
    if (!data.expires_at || typeof data.expires_at !== 'string') return false;
    
    if (data.version !== STORAGE_VERSION) {
      console.warn('Token storage version mismatch, clearing old data');
      return false;
    }
    
    if (data.hash && data.hash !== this.generateHash(data.access_token)) {
      console.warn('Token hash validation failed, possible tampering');
      return false;
    }
    
    return true;
  }

  private generateHash(token: string): string {
    let hash = 0;
    for (let i = 0; i < token.length; i++) {
      const char = token.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash).toString(16);
  }

  private clearAuth(): void {
    this.token = null;
    this.profile = null;
    
    localStorage.removeItem(STORAGE_KEYS.TOKEN);
    localStorage.removeItem(STORAGE_KEYS.PROFILE);
    localStorage.removeItem(STORAGE_KEYS.REMEMBER_ME);
    localStorage.removeItem(STORAGE_KEYS.TOKEN_SOURCE);
    
    sessionStorage.removeItem(STORAGE_KEYS.TOKEN);
    sessionStorage.removeItem(STORAGE_KEYS.PROFILE);
    sessionStorage.removeItem(STORAGE_KEYS.REMEMBER_ME);
    
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
    
    this.notifyTokenChange(null);
  }

  private startTokenRefreshMonitor(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }

    const scheduleRefresh = () => {
      if (!this.token) return;

      const expires = new Date(this.token.expires_at);
      const now = new Date();
      const timeUntilExpire = expires.getTime() - now.getTime();
      const refreshBefore = 60 * 1000;
      const refreshTime = Math.max(timeUntilExpire - refreshBefore, 0);

      this.refreshTimer = setTimeout(async () => {
        await this.refreshToken();
        scheduleRefresh();
      }, refreshTime);
    };

    scheduleRefresh();
  }

  public destroy(): void {
    this.clearAuth();
    AuthManager.instance = null as unknown as AuthManager;
  }
}

export const authManager = AuthManager.getInstance();