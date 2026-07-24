import { authApi } from './client';

export interface AuthState {
  isAuthenticated: boolean;
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
  PROFILE: 'heiman_user_profile',
};

export class AuthManager {
  private static instance: AuthManager;
  private profile: UserProfile | null = null;
  private isAuthenticatedFlag: boolean = false;
  private onAuthChangeCallbacks: Array<(authenticated: boolean) => void> = [];

  private constructor() {
    this.loadFromStorage();
  }

  public static getInstance(): AuthManager {
    if (!AuthManager.instance) {
      AuthManager.instance = new AuthManager();
    }
    return AuthManager.instance;
  }

  public getProfile(): UserProfile | null {
    return this.profile;
  }

  public isAuthenticated(): boolean {
    return this.isAuthenticatedFlag;
  }

  public async checkAuthStatus(): Promise<boolean> {
    try {
      const response = await authApi.getAuthStatus();
      if (response.data.success !== false && response.data.data?.authenticated) {
        this.isAuthenticatedFlag = true;
        await this.fetchProfile();
      } else {
        this.isAuthenticatedFlag = false;
        this.profile = null;
      }
      this.notifyAuthChange(this.isAuthenticatedFlag);
      return this.isAuthenticatedFlag;
    } catch {
      this.isAuthenticatedFlag = false;
      this.notifyAuthChange(false);
      return false;
    }
  }

  public async logout(): Promise<void> {
    this.isAuthenticatedFlag = false;
    this.profile = null;
    this.clearStorage();
    this.notifyAuthChange(false);
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

  public setAuthenticated(authenticated: boolean): void {
    this.isAuthenticatedFlag = authenticated;
    this.notifyAuthChange(authenticated);
  }

  public onAuthChange(callback: (authenticated: boolean) => void): () => void {
    this.onAuthChangeCallbacks.push(callback);
    
    return () => {
      const index = this.onAuthChangeCallbacks.indexOf(callback);
      if (index > -1) {
        this.onAuthChangeCallbacks.splice(index, 1);
      }
    };
  }

  private notifyAuthChange(authenticated: boolean): void {
    this.onAuthChangeCallbacks.forEach(callback => {
      try {
        callback(authenticated);
      } catch (error) {
        console.error('Auth change callback error:', error);
      }
    });
  }

  private async saveProfileToStorage(): Promise<void> {
    if (!this.profile) return;

    try {
      localStorage.setItem(STORAGE_KEYS.PROFILE, JSON.stringify(this.profile));
    } catch (error) {
      console.error('Failed to save profile to storage:', error);
    }
  }

  private loadFromStorage(): void {
    try {
      const profileStr = localStorage.getItem(STORAGE_KEYS.PROFILE);
      if (profileStr) {
        this.profile = JSON.parse(profileStr);
      }
    } catch (error) {
      console.error('Failed to load auth data from storage:', error);
    }
  }

  private clearStorage(): void {
    localStorage.removeItem(STORAGE_KEYS.PROFILE);
    localStorage.removeItem('heiman_access_token');
    localStorage.removeItem('heiman_refresh_token');
    localStorage.removeItem('heiman_token_expires');
    localStorage.removeItem('heiman_auth_token');
    localStorage.removeItem('heiman_token_source');
    localStorage.removeItem('heiman_remember_me');
    
    sessionStorage.removeItem(STORAGE_KEYS.PROFILE);
    sessionStorage.removeItem('heiman_auth_token');
    sessionStorage.removeItem('heiman_remember_me');
  }

  public destroy(): void {
    this.clearStorage();
    AuthManager.instance = null as unknown as AuthManager;
  }
}

export const authManager = AuthManager.getInstance();