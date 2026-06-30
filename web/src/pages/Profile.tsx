import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { User, Shield, Bell, Palette, Globe, LogOut, Edit2, Check, X } from 'lucide-react';
import { authApi } from '../api/client';

interface ProfileData {
  username: string;
  email: string;
  phone: string;
  bindStatus: boolean;
}

type Lang = 'zh' | 'en' | 'ja' | 'ko';

const langOptions: { key: Lang; label: Record<string, string> }[] = [
  { key: 'zh', label: { zh: '中文', en: 'Chinese', ja: '中国語', ko: '중국어' } },
  { key: 'en', label: { zh: 'English', en: 'English', ja: '英語', ko: '영어' } },
  { key: 'ja', label: { zh: '日本語', en: 'Japanese', ja: '日本語', ko: '일본어' } },
  { key: 'ko', label: { zh: '한국어', en: 'Korean', ja: '韓国語', ko: '한국어' } },
];

export function Profile() {
  const { t, i18n } = useTranslation('app');
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [error, setError] = useState('');
  const [showLanguageModal, setShowLanguageModal] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    setLoading(true);
    try {
      const response = await authApi.getProfile();
      const profileData = response.data?.data || response.data;
      if (profileData && typeof profileData === 'object' && !('success' in profileData)) {
        setProfile({
          username: (profileData as ProfileData).username || '',
          email: (profileData as ProfileData).email || '',
          phone: (profileData as ProfileData).phone || '',
          bindStatus: (profileData as ProfileData).bindStatus || false,
        });
      }
    } catch {
      const hasToken = !!localStorage.getItem('heiman_access_token');
      setProfile({
        username: '',
        email: '',
        phone: '',
        bindStatus: hasToken,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (field: string) => {
    if (!profile) return;
    setEditingField(field);
    setEditValue(profile[field as keyof ProfileData]?.toString() || '');
    setError('');
  };

  const handleSave = async () => {
    if (!editValue.trim()) {
      setError(t('error'));
      return;
    }
    if (!profile) return;

    const updatedProfile = { ...profile, [editingField!]: editValue };
    setProfile(updatedProfile);

    if (editingField === 'username') {
      localStorage.setItem('heiman_username', editValue);
    }
    setEditingField(null);
    setEditValue('');
  };

  const handleLanguageChange = (lang: Lang) => {
    if (lang === i18n.language) return;
    i18n.changeLanguage(lang).then(() => {
      window.location.reload();
    });
  };

  const handleHeimanBind = () => {
    window.location.href = '/api/auth/login';
  };

  const handleLogout = () => {
    if (confirm(t('logoutConfirm'))) {
      authApi.logout();
    }
  };

  const themeLabel = {
    zh: '深色模式',
    en: 'Dark Mode',
    ja: 'ダークモード',
    ko: '다크 모드',
  };

  const menuItems = [
    { icon: Shield, label: t('protection'), value: '24/7' },
    { icon: Bell, label: t('notifications'), value: t('enabled') },
    { icon: Palette, label: t('theme'), value: themeLabel[i18n.language as keyof typeof themeLabel] || 'Dark Mode' },
  ];

  if (loading) {
    return (
      <div className="max-w-[1200px] w-full mx-auto px-4 md:px-8 pt-5 pb-12">
        <div className="flex items-center justify-center h-64">
          <span className="inline-block w-2 h-2 rounded-full bg-[#00d4ff] animate-pulse" />
          {t('loading')}
        </div>
      </div>
    );
  }

  if (!profile) {
    return null;
  }

  return (
    <div className="max-w-[1200px] w-full mx-auto px-4 md:px-8 pt-5 pb-12">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white">{t('profile')}</h1>
        <p className="text-sm text-[#6b7a9a]">{t('manageHomes')}</p>
      </div>

      <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5 mb-6">
        <div className="flex items-center gap-6">
          <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center">
            <User className="w-8 h-8 text-[#0a1628]" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              {editingField === 'username' ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="px-3 py-1.5 bg-white/5 border border-[#00d4ff]/50 rounded-lg text-white focus:outline-none focus:border-[#00d4ff]"
                    autoFocus
                  />
                  <button
                    onClick={handleSave}
                    className="p-1.5 rounded-lg bg-[#00d4ff] text-[#0a1628] hover:opacity-90 transition-opacity"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setEditingField(null)}
                    className="p-1.5 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-opacity"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold text-white">{profile.username || t('unknown')}</h2>
                  <button
                    onClick={() => handleEdit('username')}
                    className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                  >
                    <Edit2 className="w-4 h-4 text-[#6b7a9a]" />
                  </button>
                </div>
              )}
            </div>
            {error && (
              <p className="text-sm text-[#ff4757] mt-1">{error}</p>
            )}
            <p className="text-sm text-[#6b7a9a] mt-1">
              {profile.bindStatus ? t('accountBinding') : t('bindAccount')}
            </p>
          </div>
        </div>

        {!profile.bindStatus && (
          <div className="mt-6 p-4 bg-[#00d4ff]/10 border border-[#00d4ff]/30 rounded-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center">
                  <User className="w-5 h-5 text-[#0a1628]" />
                </div>
                <div>
                  <p className="font-medium text-white">{t('accountBinding')}</p>
                  <p className="text-sm text-[#6b7a9a]">{t('bindAccount')}</p>
                </div>
              </div>
              <button
                onClick={handleHeimanBind}
                className="px-4 py-2 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] font-semibold rounded-lg hover:opacity-90 transition-opacity"
              >
                {t('bindAccount')}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5 mb-6">
        <h3 className="text-sm font-semibold text-white mb-4">{t('settings')}</h3>
        <div className="space-y-4">
          {menuItems.map((item, index) => (
            <div
              key={index}
              className="flex items-center justify-between p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <item.icon className="w-5 h-5 text-[#00d4ff]" />
                <span className="text-white">{item.label}</span>
              </div>
              <span className="text-[#6b7a9a]">{item.value}</span>
            </div>
          ))}
          <div
            onClick={() => setShowLanguageModal(true)}
            className="flex items-center justify-between p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <Globe className="w-5 h-5 text-[#00d4ff]" />
              <span className="text-white">{t('language')}</span>
            </div>
            <span className="text-[#6b7a9a]">
              {langOptions.find(l => l.key === i18n.language)?.label[i18n.language] || i18n.language}
            </span>
          </div>
        </div>
      </div>

      <div className="bg-[#0f2137] rounded-xl p-6 border border-white/5">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-3 p-4 bg-[#ff4757]/10 border border-[#ff4757]/30 rounded-xl text-[#ff4757] hover:bg-[#ff4757]/20 transition-colors"
        >
          <LogOut className="w-5 h-5" />
          <span>{t('logout')}</span>
        </button>
      </div>

      {showLanguageModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/50" onClick={() => setShowLanguageModal(false)} />
          <div className="relative bg-[#0f2137] rounded-xl p-6 border border-white/10 w-full max-w-md">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-white">{t('language')}</h3>
              <button onClick={() => setShowLanguageModal(false)} className="text-[#6b7a9a] hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-2">
              {langOptions.map((option) => (
                <button
                  key={option.key}
                  onClick={() => handleLanguageChange(option.key)}
                  className={`w-full flex items-center justify-between p-4 rounded-xl transition-colors ${
                    i18n.language === option.key
                      ? 'bg-[#00d4ff]/10 border border-[#00d4ff]/30'
                      : 'bg-white/5 hover:bg-white/10 border border-transparent'
                  }`}
                >
                  <span className="text-white">{option.label[i18n.language]}</span>
                  {i18n.language === option.key && (
                    <Check className="w-5 h-5 text-[#00d4ff]" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}