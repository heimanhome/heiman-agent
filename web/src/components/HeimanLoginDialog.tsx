import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { Lock, AlertCircle, Loader2, ExternalLink, X } from 'lucide-react';
import { authApi } from '../api/client';

interface Props {
  open: boolean;
  onClose?: () => void;
  onSuccess?: () => void;
}

export function HeimanLoginDialog({ open, onSuccess }: Props) {
  const { t } = useTranslation('app');
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // OAuth2 回调由后端 /api/auth/heiman_redirect 直接处理
  // 后端返回 HTML 页面自动设置 localStorage 并重定向到首页
  // 前端不需要额外处理 code 和 state

  const handleOAuthLogin = () => {
    setLoading(true);
    setError('');
    window.location.href = '/api/auth/login';
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="heiman-login-title"
        className="w-[90%] max-w-md bg-white dark:bg-[#0f2137] border border-white/10 rounded-2xl shadow-xl p-6 animate-in"
      >
        <div className="flex items-start justify-between mb-3">
          <h2 id="heiman-login-title" className="text-xl font-bold text-gray-900 dark:text-white">
            {t('login')}
          </h2>
          <button
            type="button"
            onClick={() => setError('')}
            className="rounded-full p-1 text-gray-500 dark:text-[#6b7a9a] hover:text-gray-900 dark:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="text-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center mx-auto mb-4">
            <Lock className="w-8 h-8 text-[#0a1628]" />
          </div>
          <p className="text-gray-500 dark:text-[#6b7a9a]">{t('welcomeBack')}</p>
        </div>

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
          <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">
            {t('loginHint')}
          </p>
        </div>
      </div>
    </div>
  );
}
