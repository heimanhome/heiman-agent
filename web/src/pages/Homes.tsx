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
  owner: 'bg-[#00d4ff]/10 text-[#00d4ff]',
  admin: 'bg-[#00ff88]/10 text-[#00ff88]',
  member: 'bg-[#ffa502]/10 text-[#ffa502]',
  device: 'bg-[#6b7a9a]/10 text-[#6b7a9a]',
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
          <h1 className="text-2xl font-bold text-white">{t('homeManagement')}</h1>
          <p className="text-sm text-[#6b7a9a]">{t('manageHomes')}</p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] font-semibold rounded-xl hover:opacity-90 transition-opacity"
        >
          <Plus className="w-5 h-5" />
          <span>{t('createHome')}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-[#0f2137] rounded-2xl p-4 border border-white/5">
            <h2 className="text-lg font-semibold text-white mb-4">{t('myHomes')}</h2>
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
                      ? 'bg-[#00d4ff]/10 border border-[#00d4ff]/30'
                      : 'hover:bg-white/5 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center">
                      <Home className="w-5 h-5 text-[#0a1628]" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-white">{home.name}</p>
                      <p className="text-sm text-[#6b7a9a]">{home.members.length} {t('members')}</p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-[#6b7a9a]" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          {loading ? (
            <div className="bg-[#0f2137] rounded-2xl p-12 text-center border border-white/5 animate-pulse" />
          ) : selectedHome ? (
            <div className="space-y-6">
              <div className="bg-[#0f2137] rounded-2xl p-6 border border-white/5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center">
                      <Home className="w-7 h-7 text-[#0a1628]" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white">{selectedHome.name}</h2>
                      <p className="text-sm text-[#6b7a9a]">{selectedHome.address}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                      <Edit className="w-5 h-5 text-[#6b7a9a]" />
                    </button>
                    <button className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                      <Settings className="w-5 h-5 text-[#6b7a9a]" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mt-6">
                  <div className="bg-white/5 rounded-xl p-4 text-center">
                    <Users className="w-6 h-6 text-[#00d4ff] mx-auto mb-2" />
                    <p className="text-2xl font-bold text-white">{selectedHome.members.length}</p>
                    <p className="text-sm text-[#6b7a9a]">{t('members')}</p>
                  </div>
                  <div className="bg-white/5 rounded-xl p-4 text-center">
                    <Home className="w-6 h-6 text-[#00ff88] mx-auto mb-2" />
                    <p className="text-2xl font-bold text-white">{selectedHome.devices}</p>
                    <p className="text-sm text-[#6b7a9a]">{t('devices')}</p>
                  </div>
                  <div className="bg-white/5 rounded-xl p-4 text-center">
                    <Shield className="w-6 h-6 text-[#ffa502] mx-auto mb-2" />
                    <p className="text-2xl font-bold text-white">24/7</p>
                    <p className="text-sm text-[#6b7a9a]">{t('protection')}</p>
                  </div>
                </div>
              </div>

              <div className="bg-[#0f2137] rounded-2xl p-6 border border-white/5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">{t('members')}</h3>
                  <button
                    onClick={() => setShowAddMember(!showAddMember)}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm text-[#00d4ff] bg-[#00d4ff]/10 rounded-lg hover:bg-[#00d4ff]/20 transition-colors"
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
                      className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50"
                      autoFocus
                    />
                    <div className="flex items-center gap-2 mt-3">
                      <button
                        onClick={handleAddMember}
                        disabled={!memberName.trim()}
                        className="px-4 py-2 bg-[#00d4ff] text-[#0a1628] font-semibold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {t('add')}
                      </button>
                      <button
                        onClick={() => {
                          setShowAddMember(false);
                          setMemberName('');
                        }}
                        className="px-4 py-2 text-[#6b7a9a] hover:text-white transition-colors"
                      >
                        {t('cancel')}
                      </button>
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  {selectedHome.members.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between p-4 bg-white/5 rounded-xl"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center text-[#0a1628] font-semibold">
                          {member.avatar || member.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-white">{member.name}</p>
                          <span className={`text-xs px-2 py-0.5 rounded-full ${roleColors[member.role]}`}>
                            {t(roleLabels[member.role])}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleRemoveMember(member.id)}
                        className="flex items-center gap-2 px-3 py-1.5 text-sm text-[#ff4757] bg-[#ff4757]/10 rounded-lg hover:bg-[#ff4757]/20 transition-colors"
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
            <div className="bg-[#0f2137] rounded-2xl p-12 text-center border border-white/5">
              <Home className="w-16 h-16 text-[#6b7a9a] mx-auto mb-4" />
              <p className="text-white text-lg mb-2">{t('selectHome')}</p>
              <p className="text-sm text-[#6b7a9a]">{t('selectHomeHint')}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}