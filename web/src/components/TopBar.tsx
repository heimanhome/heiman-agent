import { useTranslation } from 'react-i18next';
import { Sun, Moon, User, Globe } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { LanguageSwitcher } from './LanguageSwitcher';
import { HomeSwitcher } from './HomeSwitcher';
import { useAppStore } from '../store';
import { useEffect } from 'react';

export function TopBar() {
  const { t, i18n } = useTranslation('app');
  const { effective, toggle } = useTheme();
  const { profile, fetchProfile } = useAppStore();
  const username = profile?.nickName || profile?.username || '';

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const isDarkMode = effective === 'dark';

  return (
    <header
      className={`flex items-center justify-between gap-4 px-5 md:px-8 border-b bg-opacity-95 backdrop-blur-sm`}
      style={{ 
        minHeight: 64,
        backgroundColor: isDarkMode ? '#0f172a' : '#ffffff',
        borderColor: isDarkMode ? '#1e293b' : '#e2e8f0'
      }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <HomeSwitcher />
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {username && (
          <div className={`flex items-center gap-2 text-sm ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}>
            <User className="w-4 h-4" />
            <span className="hidden md:inline">{username}</span>
          </div>
        )}
        <LanguageSwitcher />
        <button
          type="button"
          onClick={toggle}
          className={`inline-flex items-center justify-center rounded-md transition-colors ${
            isDarkMode 
              ? 'text-slate-300 hover:bg-white/10 hover:text-white' 
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
          style={{ width: 32, height: 32 }}
          aria-label={effective === 'dark' ? t('theme.toLight') : t('theme.toDark')}
          title={effective === 'dark' ? t('theme.toLight') : t('theme.toDark')}
        >
          {effective === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>
      </div>
    </header>
  );
}
