import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Filter, Wifi } from 'lucide-react';
import { SensorCard } from '../components/SensorCard';
import { useAppStore } from '../store';
import { useNavigate } from 'react-router-dom';
import type { SensorType, SensorStatus } from '../types';

const sensorTypes: SensorType[] = ['smoke', 'temperature', 'humidity', 'co', 'water', 'contact', 'motion', 'gateway'];
const sensorStatuses: SensorStatus[] = ['normal', 'warning', 'alarm', 'offline'];

export function Sensors() {
  const { t } = useTranslation('app');
  const { sensors, loading, fetchSensors, fetchHomes, currentHomeId } = useAppStore();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<SensorType | 'all'>('all');
  const [filterStatus, setFilterStatus] = useState<SensorStatus | 'all'>('all');

  useEffect(() => {
    fetchHomes();
  }, [fetchHomes]);

  useEffect(() => {
    if (currentHomeId) {
      fetchSensors();
    }
  }, [currentHomeId, fetchSensors]);

  const filteredSensors = sensors.filter((sensor) => {
    const matchesSearch = sensor.did.toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === 'all' || sensor.sensor_type === filterType;
    const matchesStatus = filterStatus === 'all' || sensor.status === filterStatus;
    return matchesSearch && matchesType && matchesStatus;
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{t('sensors')}</h1>
          <p className="text-sm text-[#6b7a9a]">{t('manageSensors')}</p>
        </div>
      </div>

      <div className="bg-[#0f2137] rounded-xl p-4 border border-white/5">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
            <input
              type="text"
              placeholder={t('searchSensorId')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50 transition-colors"
            />
          </div>
          <div className="flex gap-4">
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value as SensorType | 'all')}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('allTypes')}</option>
                {sensorTypes.map((type) => (
                  <option key={type} value={type}>{t(`sensorLabels.${type}`)}</option>
                ))}
              </select>
            </div>
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value as SensorStatus | 'all')}
                className="pl-12 pr-8 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#00d4ff]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="all">{t('allStatus')}</option>
                {sensorStatuses.map((status) => (
                  <option key={status} value={status}>{t(`statusLabels.${status}`)}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {loading.sensors ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-[#0f2137] rounded-2xl p-5 border border-white/5 animate-pulse" />
          ))}
        </div>
      ) : filteredSensors.length === 0 ? (
        <div className="bg-[#0f2137] rounded-2xl p-12 text-center border border-white/5">
          <Wifi className="w-12 h-12 text-[#6b7a9a] mx-auto mb-4" />
          <p className="text-white mb-2">{t('noSensorData')}</p>
          <p className="text-sm text-[#6b7a9a]">{t('adjustFilter')}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSensors.map((sensor) => (
            <SensorCard
              key={sensor.did}
              sensor={sensor}
              onClick={() => navigate(`/sensors/${sensor.did}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
