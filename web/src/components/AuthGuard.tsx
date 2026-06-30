import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { authApi } from '../api/client';
import { authManager } from '../api/auth-manager';
import { useAppStore } from '../store';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const checkingRef = useRef(false);
  const dataLoadingRef = useRef(false);

  const { fetchProfile, fetchHomes, fetchSensors, fetchEvents, fetchRules } = useAppStore();

  const refreshAllData = useCallback(async () => {
    if (dataLoadingRef.current) return;
    dataLoadingRef.current = true;

    try {
      console.log('[AuthGuard] Refreshing all data after authentication...');
      await Promise.all([
        fetchProfile(true),
        fetchHomes(true),
      ]);
      await Promise.all([
        fetchSensors(true),
        fetchEvents(true),
        fetchRules(true),
      ]);
      console.log('[AuthGuard] All data refreshed successfully');
    } catch (error) {
      console.error('[AuthGuard] Failed to refresh data:', error);
    } finally {
      setDataLoaded(true);
      dataLoadingRef.current = false;
    }
  }, [fetchProfile, fetchHomes, fetchSensors, fetchEvents, fetchRules]);

  const checkAuth = useCallback(async () => {
    if (checkingRef.current) return;
    checkingRef.current = true;

    try {
      if (location.pathname === '/login' || location.pathname === '/auth/login') {
        setLoading(false);
        setIsAuthenticated(true);
        return;
      }

      if (!authManager.isAuthenticated()) {
        const token = authManager.getToken();
        if (token && token.refresh_token) {
          try {
            const newToken = await authManager.refreshToken();
            if (!newToken) {
              setLoading(false);
              setIsAuthenticated(false);
              return;
            }
          } catch {
            setLoading(false);
            setIsAuthenticated(false);
            return;
          }
        } else {
          setLoading(false);
          setIsAuthenticated(false);
          return;
        }
      }

      try {
        const response = await authApi.getToken();
        if (response.data.success !== false && response.data.data?.access_token) {
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
        }
      } catch (error: unknown) {
        const axiosError = error as { status?: number };
        if (axiosError.status === 401) {
          setIsAuthenticated(false);
        } else {
          setIsAuthenticated(true);
        }
      }
    } finally {
      setLoading(false);
      checkingRef.current = false;
    }
  }, [location.pathname]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (isAuthenticated && !loading && !dataLoaded) {
      refreshAllData();
    }
  }, [isAuthenticated, loading, dataLoaded, refreshAllData]);

  useEffect(() => {
    const unsubscribe = authManager.onTokenChange((token) => {
      setIsAuthenticated(!!token);
      if (token && !dataLoaded) {
        refreshAllData();
      }
    });
    return unsubscribe;
  }, [dataLoaded, refreshAllData]);

  useEffect(() => {
    if (!loading && !isAuthenticated && location.pathname !== '/login' && location.pathname !== '/auth/login') {
      navigate('/login', { replace: true, state: { from: location.pathname } });
    }
  }, [loading, isAuthenticated, navigate, location.pathname]);

  if (loading || !dataLoaded) {
    return (
      <div className="min-h-screen bg-[#060d17] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-[#00d4ff] animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}
