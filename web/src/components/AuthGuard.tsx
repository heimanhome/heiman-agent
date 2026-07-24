import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAppStore } from '../store';
import { authManager } from '../api/auth-manager';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const dataLoadingRef = useRef(false);
  const navigate = useNavigate();

  const { fetchProfile, fetchHomes, fetchSensors, fetchEvents, fetchRules } = useAppStore();

  const loadAllData = useCallback(async () => {
    if (dataLoadingRef.current) return;
    dataLoadingRef.current = true;

    try {
      await Promise.all([
        fetchProfile(true),
        fetchHomes(true),
      ]);
      await Promise.all([
        fetchSensors(true),
        fetchEvents(true),
        fetchRules(true),
      ]);
    } catch (error) {
      console.error('[AuthGuard] Failed to refresh data:', error);
    } finally {
      setLoading(false);
      dataLoadingRef.current = false;
    }
  }, [fetchProfile, fetchHomes, fetchSensors, fetchEvents, fetchRules]);

  useEffect(() => {
    (async () => {
      try {
        const isAuthed = await authManager.checkAuthStatus();
        if (!isAuthed) {
          setAuthenticated(false);
          setLoading(false);
          navigate('/login', { replace: true });
          return;
        }
        setAuthenticated(true);
        await loadAllData();
      } catch (error) {
        console.error('[AuthGuard] Auth check failed:', error);
        setAuthenticated(false);
        setLoading(false);
        navigate('/login', { replace: true });
      }
    })();
  }, [loadAllData, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#060d17] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-[#00d4ff] animate-spin" />
      </div>
    );
  }

  if (!authenticated) {
    return null;
  }

  return <>{children}</>;
}
