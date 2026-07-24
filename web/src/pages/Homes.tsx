import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Home, Plus, Users, Settings, Trash2, Edit, ChevronRight, Shield, UserPlus, UserMinus } from 'lucide-react';
import { homeApi, type HomeData, type Member } from '../api/client';
import { useAppStore } from '../store';

const roleLabels: Record<string, string> = {
  owner: 'roleOwner',
  admin: 'roleAdmin',
  member: 'roleMember',
  device: 'device',
};

const roleColors: Record<string, string> = {
  owner: 'bg-blue-100 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400',
  admin: 'bg-green-100 text-green-600 dark:bg-green-900/20 dark:text-green-400',
  member: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  device: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500',
};

export function Homes() {
  const { t } = useTranslation('app');
  const { switchHome } = useAppStore();
  const [homes, setHomes] = useState<HomeData[]>([]);
  const [selectedHome, setSelectedHome] = useState<HomeData | null>(null);
  const [showAddMember, setShowAddMember] = useState(false);
  const [memberName, setMemberName] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchHomes = async () => {
    setLoading(true);
    try {
      const response = await homeApi.getAll();
      const rawData = response.data?.data || response.data || [];
      const data = Array.isArray(rawData) ? rawData : [];
      setHomes(data);
      if (data.length > 0 && !selectedHome) {
        setSelectedHome(data[0]);
      }
    } catch (error) {
      console.error('Failed to fetch homes:', error);
      setHomes([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHomes();
  }, []);

  const fetchHomeDetail = async (homeId: string) => {
    try {
      const response = await homeApi.getById(homeId);
      const homeData = response.data?.data;
      if (homeData) {
        setSelectedHome(homeData as HomeData);
        setHomes(prev => prev.map(h => h.id === homeId ? { ...h, ...homeData } : h));
      }
    } catch (error) {
      console.error('Failed to fetch home detail:', error);
    }
  };

  const handleSelectHome = async (home: HomeData) => {
    setSelectedHome(home);
    await switchHome(home.id);
    await fetchHomeDetail(home.id);
  };

  const handleAddMember = async () => {
    if (!selectedHome || !memberName.trim()) return;
    try {
      await homeApi.addMember(selectedHome.id, { name: memberName, role: 'member' });
      await fetchHomes();
    } catch (error) {
      console.error('Failed to add member:', error);
    } finally {
      setMemberName('');
      setShowAddMember(false);
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    if (!selectedHome) return;
    try {
      await homeApi.removeMember(selectedHome.id, memberId);
      await fetchHomes();
    } catch (error) {
      console.error('Failed to remove member:', error);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('homeManagement')}</h1>
          <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('manageHomes')}</p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-semibold rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          <span>{t('createHome')}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-4 border border-gray-200 dark:border-white/5">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('myHomes')}</h2>
            <div className="space-y-2">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="w-full text-left p-4 rounded-xl bg-white/5 border border-transparent animate-pulse" />
                ))
              ) : homes.map((home) => (
                <button
                  key={home.id}
                  onClick={() => handleSelectHome(home)}
                  className={`w-full text-left p-4 rounded-xl transition-all ${
                    selectedHome?.id === home.id
                      ? 'bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-800/50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                      <Home className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-white">{home.name}</p>
                      <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">{home.members.length} {t('members')}</p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-500 dark:text-[#6b7a9a]" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          {loading ? (
            <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-12 text-center border border-gray-200 dark:border-white/5 animate-pulse" />
          ) : selectedHome ? (
            <div className="space-y-6">
              <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-6 border border-gray-200 dark:border-white/5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                        <Home className="w-7 h-7 text-gray-600 dark:text-gray-400" />
                      </div>
                    <div>
                      <h2 className="text-xl font-bold text-gray-900 dark:text-white">{selectedHome.name}</h2>
                      <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">{selectedHome.address}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
                      <Edit className="w-5 h-5 text-gray-900 dark:text-white" />
                    </button>
                    <button className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
                      <Settings className="w-5 h-5 text-gray-900 dark:text-white" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mt-6">
                  <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 text-center">
                    <Users className="w-6 h-6 text-gray-500 dark:text-gray-400 mx-auto mb-2" />
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{selectedHome.members.length}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{t('members')}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 text-center">
                    <Home className="w-6 h-6 text-gray-500 dark:text-gray-400 mx-auto mb-2" />
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{selectedHome.devices}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{t('devices')}</p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 text-center">
                    <Shield className="w-6 h-6 text-gray-500 dark:text-gray-400 mx-auto mb-2" />
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">24/7</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{t('protection')}</p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-6 border border-gray-200 dark:border-white/5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{t('members')}</h3>
                  <button
          onClick={() => setShowAddMember(!showAddMember)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
                    <UserPlus className="w-4 h-4" />
                    <span>{t('addMember')}</span>
                  </button>
                </div>

                {showAddMember && (
                  <div className="bg-white/5 rounded-xl p-4 mb-4">
                    <input
                        type="text"
                        value={memberName}
                        onChange={(e) => setMemberName(e.target.value)}
                        placeholder={t('enterMemberName')}
                        className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:border-gray-400 dark:focus:border-gray-500"
                        autoFocus
                      />
                    <div className="flex items-center gap-2 mt-3">
                      <button
                    onClick={handleAddMember}
                    disabled={!memberName.trim()}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-semibold rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {t('add')}
                  </button>
                  <button
                    onClick={() => {
                      setShowAddMember(false);
                      setMemberName('');
                    }}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700"
                  >
                    {t('cancel')}
                  </button>
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  {(selectedHome?.members || []).map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between p-4 bg-white/5 rounded-xl"
                    >
                      <div className="flex items-center gap-3">
                        <div className="relative w-10 h-10 rounded-full">
                          <div className="absolute inset-0 rounded-full bg-gradient-to-br from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600 flex items-center justify-center text-gray-700 dark:text-gray-300 font-semibold">
                            {member.name.charAt(0).toUpperCase()}
                          </div>
                          {(() => {
                            const avatarUrl = typeof member.avatar === 'string'
                              ? (member.avatar.startsWith('http') ? member.avatar : null)
                              : (member.avatar?.url || null);
                            return avatarUrl ? (
                              <img
                                src={avatarUrl}
                                alt={member.name}
                                className="w-10 h-10 rounded-full object-cover"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = 'none';
                                }}
                              />
                            ) : null;
                          })()}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white">{member.name}</p>
                          <span className={`text-xs px-2 py-0.5 rounded-full ${roleColors[member.role]}`}>
                            {t(roleLabels[member.role])}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleRemoveMember(member.id)}
                        className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                      >
                        <UserMinus className="w-4 h-4" />
                        <span>{t('remove')}</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-12 text-center border border-gray-200 dark:border-white/5">
              <Home className="w-16 h-16 text-gray-500 dark:text-[#6b7a9a] mx-auto mb-4" />
              <p className="text-gray-900 dark:text-white text-lg mb-2">{t('selectHome')}</p>
              <p className="text-sm text-gray-500 dark:text-[#6b7a9a]">{t('selectHomeHint')}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}