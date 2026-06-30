import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { Lock, AlertCircle, Loader2, ExternalLink } from 'lucide-react';
import { authApi } from '../api/client';

export function Login() {
  const { t } = useTranslation('app');
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    
    if (code && state) {
      setLoading(true);
      fetch(`/api/auth/heiman_redirect?code=${code}&state=${state}`)
        .then(res => res.text())
        .then(html => {
          document.open();
          document.write(html);
          document.close();
        })
        .catch(() => {
          setError(t('loginFailed'));
          setLoading(false);
        });
    }
  }, [searchParams, t]);

  const handleOAuthLogin = () => {
    window.location.href = '/api/auth/login';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#060d17] via-[#0a1628] to-[#0f2137] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center mx-auto mb-4">
            <Lock className="w-8 h-8 text-[#0a1628]" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">{t('login')}</h1>
          <p className="text-[#6b7a9a]">{t('welcomeBack')}</p>
        </div>

        <div className="bg-[#0f2137]/80 backdrop-blur-lg rounded-2xl p-6 border border-white/10 shadow-xl">
          {error && (
            <div className="flex items-center gap-2 px-4 py-3 bg-[#ff4757]/10 border border-[#ff4757]/30 rounded-xl mb-4">
              <AlertCircle className="w-5 h-5 text-[#ff4757]" />
              <span className="text-sm text-[#ff4757]">{error}</span>
            </div>
          )}

          <div className="space-y-4">
            <button
              type="button"
              onClick={handleOAuthLogin}
              disabled={loading}
              className="w-full py-4 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>{t('loading')}</span>
                </>
              ) : (
                <>
                  <div className="w-5 h-5 rounded-full bg-[#0a1628] flex items-center justify-center">
                    <span className="text-xs font-bold text-[#00d4ff]">H</span>
                  </div>
                  <span>{t('loginWithHeiman')}</span>
                  <ExternalLink className="w-4 h-4" />
                </>
              )}
            </button>
          </div>

          <div className="mt-6 text-center">
            <p className="text-sm text-[#6b7a9a]">
              {t('loginHint')}
            </p>
          </div>
        </div>

        <p className="text-center text-sm text-[#6b7a9a] mt-6">
          {t('noAccount')}
          <button
            type="button"
            onClick={handleOAuthLogin}
            className="ml-1 text-[#00d4ff] hover:text-[#00ff88] transition-colors"
          >
            {t('signUp')}
          </button>
        </p>
      </div>
    </div>
  );
}
