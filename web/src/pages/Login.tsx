import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Lock, AlertCircle, Loader2, ExternalLink, Shield, ArrowLeft } from 'lucide-react';

export function Login() {
  const { t } = useTranslation('app');
  const navigate = useNavigate();
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

  const handleBack = () => {
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#060d17] via-[#0a1628] to-[#0f2137] flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-[#00d4ff]/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/2 -left-40 w-96 h-96 bg-[#00ff88]/15 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute -bottom-40 right-1/4 w-72 h-72 bg-[#ffa502]/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTMwIDBjMTYuNTY5IDAgMzAgMTMuNDMxIDMwIDMwIDAgMTYuNTY5LTEzLjQzMSAzMC0zMCAzMEMxMy40MzEgNjAgMCA0Ni41NjkgMCAzMCAwIDEzLjQzMSAxMy40MzEgMCAzMCAwem0wIDU2Yy0xNC4zNjkgMC0yNi0xMS42MzEtMjYtMjYgMC0xNC4zNjkgMTEuNjMxLTI2IDI2LTI2IDE0LjM2OSAwIDI2IDExLjYzMSAyNiAyNiAwIDE0LjM2OS0xMS42MzEgMjYtMjYgMjZ6Ii8+PC9nPjwvZz48L3N2Zz4=')] opacity-50" />

      <div className="relative z-10 w-full max-w-md">
        <button
          onClick={handleBack}
          className="flex items-center gap-2 text-[#6b7a9a] hover:text-white transition-colors mb-6 group"
        >
          <ArrowLeft className="w-5 h-5 group-hover:-translate-x-1 transition-transform" />
          <span className="text-sm">{t('back')}</span>
        </button>

        <div className="text-center mb-8">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center mx-auto mb-6 shadow-lg shadow-[#00d4ff]/25">
            <Lock className="w-10 h-10 text-[#0a1628]" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">{t('login')}</h1>
          <p className="text-[#6b7a9a]">{t('welcomeBack')}</p>
        </div>

        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10 shadow-2xl shadow-black/20">
          {error && (
            <div className="flex items-center gap-3 px-4 py-3 bg-[#ff4757]/10 border border-[#ff4757]/30 rounded-xl mb-6 animate-fadeIn">
              <AlertCircle className="w-5 h-5 text-[#ff4757] shrink-0" />
              <span className="text-sm text-[#ff4757]">{error}</span>
            </div>
          )}

          <button
            type="button"
            onClick={handleOAuthLogin}
            disabled={loading}
            className="w-full py-4 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] font-semibold rounded-xl hover:opacity-90 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 shadow-lg shadow-[#00d4ff]/25"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>{t('loading')}</span>
              </>
            ) : (
              <>
                <div className="w-8 h-8 rounded-full bg-[#0a1628] flex items-center justify-center">
                  <span className="text-xs font-bold text-[#00d4ff]">H</span>
                </div>
                <span>{t('loginWithHeiman')}</span>
                <ExternalLink className="w-4 h-4" />
              </>
            )}
          </button>

          <div className="mt-6 text-center">
            <p className="text-sm text-[#6b7a9a]">
              {t('loginHint')}
            </p>
          </div>

          <div className="mt-8">
            <div className="flex items-center gap-3 px-4 py-3 bg-[#00d4ff]/5 border border-[#00d4ff]/10 rounded-xl">
              <Shield className="w-5 h-5 text-[#00d4ff] shrink-0" />
              <div className="text-sm">
                <p className="text-white font-medium">{t('secureConnection')}</p>
                <p className="text-[#6b7a9a]">{t('encryptedData')}</p>
              </div>
            </div>
          </div>
        </div>

        <p className="text-center text-sm text-[#6b7a9a] mt-8">
          {t('noAccount')}
          <button
            type="button"
            onClick={handleOAuthLogin}
            className="ml-1 text-[#00d4ff] hover:text-[#00ff88] transition-colors font-medium"
          >
            {t('signUp')}
          </button>
        </p>

        <div className="flex justify-center gap-8 mt-8 text-xs text-[#6b7a9a]">
          <a href="#privacy" className="hover:text-white transition-colors">{t('privacy')}</a>
          <a href="#terms" className="hover:text-white transition-colors">{t('terms')}</a>
        </div>
      </div>
    </div>
  );
}