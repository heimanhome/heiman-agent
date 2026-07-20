import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Flame, Thermometer, Droplets, Wind, AlertTriangle, Wifi, WifiOff } from 'lucide-react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js';
import { sensorApi } from '../api/client';
import { useTranslation } from 'react-i18next';
import { useAppStore } from '../store';
import type { SensorData, SensorHistoryData } from '../types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const sensorIcons: Record<string, typeof Flame> = {
  smoke: Flame,
  temperature: Thermometer,
  humidity: Droplets,
  co: Wind,
  water: Droplets,
};

const statusClasses: Record<string, { dot: string; text: string; bg: string; label: string }> = {
  normal: {
    dot: 'bg-[#00ff88]',
    text: 'text-[#00ff88]',
    bg: 'bg-[#00ff88]/10',
    label: 'normal',
  },
  warning: {
    dot: 'bg-[#ffa502]',
    text: 'text-[#ffa502]',
    bg: 'bg-[#ffa502]/10',
    label: 'warning',
  },
  alarm: {
    dot: 'bg-[#ff4757]',
    text: 'text-[#ff4757]',
    bg: 'bg-[#ff4757]/10',
    label: 'alarm',
  },
  offline: {
    dot: 'bg-[#6b7a9a]',
    text: 'text-gray-500 dark:text-[#6b7a9a]',
    bg: 'bg-[#6b7a9a]/10',
    label: 'offline',
  },
};

const getSwitchStateLabel = (state: number | undefined): string => {
  const states: Record<number, string> = {
    0: 'off',
    1: 'on',
    2: 'alarm',
    3: 'bypass',
  };
  return states[state ?? -1] ?? 'unknown';
};

const getContactStateLabel = (state: number | undefined): string => {
  const states: Record<number, string> = {
    0: 'closed',
    1: 'open',
    2: 'alarm',
  };
  return states[state ?? -1] ?? 'unknown';
};

export function SensorDetail() {
  const { did } = useParams<{ did: string }>();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation('app');
  const { currentHomeId } = useAppStore();
  const [sensor, setSensor] = useState<SensorData | null>(null);
  const [history, setHistory] = useState<SensorHistoryData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!did) return;

    const fetchData = async () => {
      setLoading(true);
      try {
        const [sensorRes, historyRes] = await Promise.all([
          sensorApi.getById(did, currentHomeId),
          sensorApi.getHistory(did, { limit: 24 }),
        ]);
        setSensor(sensorRes.data.data);
        setHistory(historyRes.data.data);
      } catch {
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [did, currentHomeId]);

  if (loading) {
    return (
      <div className="p-6">
        <button
          onClick={() => navigate('/sensors')}
          className="flex items-center gap-2 text-[#00d4ff] mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          {t('back')}
        </button>
        <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-8 border border-gray-200 dark:border-white/5 animate-pulse" />
      </div>
    );
  }

  if (!sensor) {
    return (
      <div className="p-6">
        <button
          onClick={() => navigate('/sensors')}
          className="flex items-center gap-2 text-[#00d4ff] mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          {t('back')}
        </button>
        <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-12 text-center border border-gray-200 dark:border-white/5">
          <AlertTriangle className="w-12 h-12 text-gray-500 dark:text-[#6b7a9a] mx-auto mb-4" />
          <p className="text-gray-900 dark:text-white">{t('sensorNotFound')}</p>
        </div>
      </div>
    );
  }

  const Icon = sensorIcons[sensor.sensor_type] || Wifi;
  const statusKey = sensor.status?.toLowerCase() || 'offline';
  const status = statusClasses[statusKey as keyof typeof statusClasses] || statusClasses.offline;
  const isOnline = statusKey !== 'offline';

  const getValueLabel = (sensorType: string): string => {
    const labels: Record<string, string> = {
      temperature: t('temperature'),
      humidity: t('humidity'),
      co: t('co'),
      water: t('water'),
      smoke: t('smoke'),
      contact: t('contactState'),
      motion: t('motionState'),
      plug: t('switchState'),
    };
    return labels[sensorType] || t('value');
  };

  const chartData = {
    labels: history.map((h) => new Date(h.timestamp).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })),
    datasets: [
      {
        label: `${getValueLabel(sensor.sensor_type)} (${sensor.unit || history[0]?.unit || ''})`,
        data: history.map((h) => h.value),
        borderColor: '#00d4ff',
        backgroundColor: 'rgba(0, 212, 255, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#00d4ff',
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        display: false,
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: {
          color: '#6b7a9a',
        },
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: {
          color: '#6b7a9a',
        },
      },
    },
  };

  return (
    <div className="p-6 space-y-6">
      <button
        onClick={() => navigate('/sensors')}
        className="flex items-center gap-2 text-[#00d4ff] hover:underline"
      >
        <ArrowLeft className="w-5 h-5" />
        {t('back')}
      </button>

      <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-6 border border-gray-200 dark:border-white/5">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className={`${status.bg} w-16 h-16 rounded-2xl flex items-center justify-center`}>
              <Icon className={`w-8 h-8 ${status.text}`} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                {sensor.name || t(`sensorLabels.${sensor.sensor_type}`)}
              </h1>
              <p className="text-sm text-gray-500 dark:text-[#6b7a9a] mt-1">{t('sensorId')}: {sensor.did}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {isOnline ? (
              <Wifi className="w-6 h-6 text-[#00ff88]" />
            ) : (
              <WifiOff className="w-6 h-6 text-gray-500 dark:text-[#6b7a9a]" />
            )}
            <span className={`text-sm font-medium ${status.text}`}>{t(status.label)}</span>
            <div className={`w-3 h-3 rounded-full ${status.dot} ${statusKey === 'ALARM' || statusKey === 'WARNING' ? 'animate-pulse' : ''}`} />
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('currentValue')}</p>
            <p className="text-xs text-gray-400 dark:text-[#4a5568] mb-1">{getValueLabel(sensor.sensor_type)}</p>
            <p className={`text-2xl font-bold ${status.text}`}>
              {!isOnline || sensor.value === null || sensor.value === undefined
                ? '--'
                : sensor.value === 0
                  ? t('valueZero')
                  : sensor.value}
              {isOnline && sensor.value !== 0 && sensor.unit && (
                <span className="text-sm font-normal text-gray-500 dark:text-[#6b7a9a] ml-1">{sensor.unit}</span>
              )}
            </p>
          </div>
          <div className="bg-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('sensorType')}</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">{t(`sensorLabels.${sensor.sensor_type}`)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('sensorStatusLabel')}</p>
            <p className={`text-lg font-semibold ${status.text}`}>{t(status.label)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('lastUpdate')}</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">
              {new Date(sensor.timestamp).toLocaleString(i18n.language)}
            </p>
          </div>
        </div>

        <div className="mt-6">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-[#6b7a9a] mb-4">{t('deviceProperties')}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {sensor.battery !== undefined && sensor.battery !== null && sensor.battery >= 0 && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('battery')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {sensor.battery}%
                </p>
              </div>
            )}
            {sensor.rssi !== undefined && sensor.rssi !== null && sensor.rssi > -999 && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('signalStrength')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {sensor.rssi} dBm
                </p>
              </div>
            )}
            {sensor.signalLevel !== undefined && sensor.signalLevel !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('signalLevel')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {sensor.signalLevel}
                </p>
              </div>
            )}
            {sensor.switchState !== undefined && sensor.switchState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('switchState')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {t(getSwitchStateLabel(sensor.switchState))}
                </p>
              </div>
            )}
            {sensor.contactState !== undefined && sensor.contactState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('contactState')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {t(getContactStateLabel(sensor.contactState))}
                </p>
              </div>
            )}
            {sensor.motionState !== undefined && sensor.motionState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('motionState')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {sensor.motionState === 1 ? t('motionDetected') : t('noMotion')}
                </p>
              </div>
            )}
            {sensor.gasState !== undefined && sensor.gasState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('gasState')}</p>
                <p className={`text-lg font-semibold ${sensor.gasState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]'}`}>
                  {sensor.gasState === 1 ? t('gasAlarm') : t('gasNormal')}
                </p>
              </div>
            )}
            {sensor.smokeState !== undefined && sensor.smokeState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('smokeState')}</p>
                <p className={`text-lg font-semibold ${sensor.smokeState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]'}`}>
                  {sensor.smokeState === 1 ? t('smokeAlarm') : t('smokeNormal')}
                </p>
              </div>
            )}
            {sensor.waterState !== undefined && sensor.waterState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('waterState')}</p>
                <p className={`text-lg font-semibold ${sensor.waterState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]'}`}>
                  {sensor.waterState === 1 ? t('waterLeak') : t('waterNormal')}
                </p>
              </div>
            )}
            {sensor.temperature !== undefined && sensor.temperature !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('temperature')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {sensor.temperature}°C
                </p>
              </div>
            )}
            {sensor.humidity !== undefined && sensor.humidity !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('humidity')}</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {sensor.humidity}%
                </p>
              </div>
            )}
            {sensor.alarmState !== undefined && sensor.alarmState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('alarmState')}</p>
                <p className={`text-lg font-semibold ${sensor.alarmState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]'}`}>
                  {sensor.alarmState === 1 ? t('alarm') : t('normal')}
                </p>
              </div>
            )}
            {sensor.tamperState !== undefined && sensor.tamperState !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('tamperState')}</p>
                <p className={`text-lg font-semibold ${sensor.tamperState === 1 ? 'text-[#ffa502]' : 'text-[#00ff88]'}`}>
                  {sensor.tamperState === 1 ? t('tampered') : t('normal')}
                </p>
              </div>
            )}
            {sensor.sensorLifeStatus !== undefined && sensor.sensorLifeStatus !== null && (
              <div className="bg-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{t('sensorLifeStatus')}</p>
                <p className={`text-lg font-semibold ${sensor.sensorLifeStatus === 1 ? 'text-[#ffa502]' : 'text-[#00ff88]'}`}>
                  {sensor.sensorLifeStatus === 1 ? t('sensorLifeWarning') : t('sensorLifeNormal')}
                </p>
              </div>
            )}
          </div>
        </div>

        {sensor.properties && sensor.properties.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-gray-500 dark:text-[#6b7a9a] mb-4">{t('dynamicProperties')}</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {sensor.properties.map((prop) => {
                const numValue = parseFloat(prop.value);
                let displayValue = prop.value;
                let colorClass = 'text-gray-900 dark:text-white';
                
                if (!isNaN(numValue)) {
                  displayValue = numValue.toString();
                  
                  if (prop.property_id.includes('State') || prop.property_id.includes('state')) {
                    if (numValue === 0) {
                      colorClass = 'text-[#00ff88]';
                    } else if (numValue === 1 || numValue === 2) {
                      colorClass = 'text-[#ff4757]';
                    } else {
                      colorClass = 'text-[#ffa502]';
                    }
                  }
                }
                
                return (
                  <div key={prop.property_id} className="bg-white/5 rounded-xl p-4">
                    <p className="text-xs text-gray-500 dark:text-[#6b7a9a] mb-1">{prop.property_name || prop.property_id}</p>
                    <p className={`text-lg font-semibold ${colorClass}`}>
                      {displayValue}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-[#0f2137] rounded-2xl p-6 border border-gray-200 dark:border-white/5">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('historyData')}</h2>
        {history.length === 0 ? (
          <div className="h-64 flex items-center justify-center">
            <p className="text-gray-500 dark:text-[#6b7a9a]">{t('noHistoryData')}</p>
          </div>
        ) : (
          <div className="h-64">
            <Line data={chartData} options={chartOptions} />
          </div>
        )}
      </div>
    </div>
  );
}
