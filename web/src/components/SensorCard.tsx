import { useTranslation } from 'react-i18next';
import { 
  Flame, Thermometer, Droplets, Wind, AlertTriangle, Wifi, WifiOff, 
  DoorOpen, Zap, Volume2, Circle, Router, Gamepad2, Battery, BatteryLow, BatteryMedium, BatteryFull, MapPin
} from 'lucide-react';
import type { SensorData } from '../types';

interface SensorCardProps {
  sensor: SensorData;
  onClick?: () => void;
}

function BatteryIcon({ level, isLow }: { level: number; isLow: boolean }) {
  if (level < 0) return null;
  const color = isLow || level <= 20 ? 'text-[#ff4757]' : level <= 50 ? 'text-[#ffa502]' : 'text-[#00ff88]';
  const Icon = level <= 20 ? BatteryLow : level <= 50 ? BatteryMedium : BatteryFull;
  return (
    <div className={`flex items-center gap-1 ${color}`}>
      <Icon className="w-3.5 h-3.5" />
      <span className="text-[11px] font-medium">{level}%</span>
    </div>
  );
}

function SignalIcon({ rssi }: { rssi: number }) {
  if (rssi <= -999) return null;
  
  let bars = 0;
  let color = 'text-[#6b7a9a]';
  
  if (rssi >= -50) {
    bars = 4;
    color = 'text-[#00ff88]';
  } else if (rssi >= -65) {
    bars = 3;
    color = 'text-[#00ff88]';
  } else if (rssi >= -75) {
    bars = 2;
    color = 'text-[#ffa502]';
  } else if (rssi >= -85) {
    bars = 1;
    color = 'text-[#ff4757]';
  } else {
    bars = 0;
    color = 'text-[#ff4757]';
  }

  return (
    <div className={`flex items-center gap-0.5 ${color}`}>
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className={`w-1 rounded-sm transition-colors ${
            i <= bars ? 'bg-current' : 'bg-white/10'
          }`}
          style={{ height: `${4 + i * 2}px` }}
        />
      ))}
    </div>
  );
}

const sensorIcons: Record<string, typeof Flame> = {
  smoke: Flame,
  temperature: Thermometer,
  humidity: Droplets,
  co: Wind,
  water: Droplets,
  contact: DoorOpen,
  motion: Zap,
  plug: Zap,
  siren: Volume2,
  button: Circle,
  gateway: Router,
  remote: Gamepad2,
};

const statusColors = {
  normal: {
    dot: 'bg-[#00ff88]',
    text: 'text-[#00ff88]',
    bg: 'bg-[#00ff88]/10',
    pulse: '',
  },
  warning: {
    dot: 'bg-[#ffa502]',
    text: 'text-[#ffa502]',
    bg: 'bg-[#ffa502]/10',
    pulse: 'animate-pulse',
  },
  alarm: {
    dot: 'bg-[#ff4757]',
    text: 'text-[#ff4757]',
    bg: 'bg-[#ff4757]/10',
    pulse: 'animate-pulse',
  },
  offline: {
    dot: 'bg-[#6b7a9a]',
    text: 'text-[#6b7a9a]',
    bg: 'bg-[#6b7a9a]/10',
    pulse: '',
  },
  lowBattery: {
    dot: 'bg-[#ff4757]',
    text: 'text-[#ff4757]',
    bg: 'bg-[#ff4757]/10',
    pulse: 'animate-pulse',
  },
  open: {
    dot: 'bg-[#00d4ff]',
    text: 'text-[#00d4ff]',
    bg: 'bg-[#00d4ff]/10',
    pulse: '',
  },
  closed: {
    dot: 'bg-[#00ff88]',
    text: 'text-[#00ff88]',
    bg: 'bg-[#00ff88]/10',
    pulse: '',
  },
  triggered: {
    dot: 'bg-[#00d4ff]',
    text: 'text-[#00d4ff]',
    bg: 'bg-[#00d4ff]/10',
    pulse: '',
  },
};

type StatusKey = keyof typeof statusColors;

interface StatusInfo {
  key: StatusKey;
  text: string;
  color: string;
  isAlarm: boolean;
}

export function SensorCard({ sensor, onClick }: SensorCardProps) {
  const { t, i18n } = useTranslation('app');
  const Icon = sensorIcons[sensor.sensor_type] || Wifi;
  const status = sensor.status?.toLowerCase() || 'offline';
  const isOffline = status === 'offline';
  const isOnline = !isOffline;
  const isLowBattery = sensor.battery !== null && sensor.battery !== undefined && sensor.battery >= 0 && sensor.battery <= 20;

  const numericTypes = new Set(['temperature', 'humidity', 'co', 'co2', 'pm25', 'pm10', 'hcho']);
  const defaultUnits: Record<string, string> = {
    temperature: '℃',
    humidity: '%',
    co: 'ppm',
    co2: 'ppm',
    pm25: 'μg/m³',
    pm10: 'μg/m³',
    hcho: 'mg/m³',
  };

  const sensorType = sensor.sensor_type?.toLowerCase() || '';
  const isNumeric = numericTypes.has(sensorType);
  const displayUnit = (sensor.unit && String(sensor.unit).trim()) || defaultUnits[sensorType] || '';

  const getNumericValue = (): { text: string; isValid: boolean } => {
    const raw = sensor.value as number | string | null | undefined;
    if (raw === null || raw === undefined) {
      return { text: '--', isValid: false };
    }
    const str = typeof raw === 'string' ? raw.trim() : String(raw);
    if (str === '') {
      return { text: '--', isValid: false };
    }
    const num = typeof raw === 'number' ? raw : parseFloat(str);
    if (!Number.isFinite(num)) {
      return { text: '--', isValid: false };
    }
    const formatted = Number.isInteger(num) ? num.toString() : num.toFixed(1);
    return { text: formatted, isValid: true };
  };

  const renderPrimaryValue = (): { text: string; sub?: string } => {
    if (isNumeric) {
      const { text, isValid } = getNumericValue();
      if (!isValid) return { text: '--' };
      return { text, sub: displayUnit };
    }

    const value = parseFloat(String(sensor.value)) || 0;
    switch (sensorType) {
      case 'smoke':
        return { text: t('deviceStatus.smoke.0') };
      case 'water':
        return { text: value === 1 ? t('deviceStatus.water.1') : t('deviceStatus.water.0') };
      case 'contact':
      case 'door':
      case 'window':
        return { text: value === 1 ? t('deviceStatus.open') : t('deviceStatus.closed') };
      case 'motion':
      case 'pir':
        return { text: value === 1 ? t('deviceStatus.motion.1') : t('deviceStatus.motion.0') };
      case 'button':
        return { text: value === 1 ? t('deviceStatus.sos.1') : t('deviceStatus.sos.0') };
      case 'siren':
        return { text: value === 1 ? t('deviceStatus.alarm') : t('deviceStatus.normal') };
      case 'plug':
        return { text: value === 1 ? t('deviceStatus.open') : t('deviceStatus.closed') };
      case 'gateway':
        return { text: t('deviceStatus.normal') };
      case 'remote':
        return { text: t('deviceStatus.normal') };
      default:
        if (status === 'alarm') return { text: t('deviceStatus.alarm') };
        if (status === 'warning') return { text: t('deviceStatus.warning') };
        return { text: t('deviceStatus.normal') };
    }
  };

  const getStatusInfo = (): StatusInfo => {
    if (isOffline) {
      return { key: 'offline', text: t('deviceStatus.offline'), color: 'text-[#6b7a9a]', isAlarm: false };
    }

    if (isLowBattery) {
      return { key: 'lowBattery', text: t('deviceStatus.lowBattery'), color: 'text-[#ff4757]', isAlarm: true };
    }

    if (sensor.tamperState !== null && sensor.tamperState !== undefined) {
      const tamperVal = String(sensor.tamperState);
      const text = ((t('deviceStatus.tamper') as unknown) as Record<string, string>)[tamperVal] || t('deviceStatus.tamper.0');
      return { 
        key: sensor.tamperState === 1 ? 'alarm' : 'normal',
        text, 
        color: sensor.tamperState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]',
        isAlarm: sensor.tamperState === 1 
      };
    }

    if (sensor.sensorLifeStatus !== null && sensor.sensorLifeStatus !== undefined) {
      const lifeVal = String(sensor.sensorLifeStatus);
      const text = ((t('deviceStatus.sensorLife') as unknown) as Record<string, string>)[lifeVal] || t('deviceStatus.sensorLife.0');
      return { 
        key: sensor.sensorLifeStatus === 1 ? 'warning' : 'normal',
        text, 
        color: sensor.sensorLifeStatus === 1 ? 'text-[#ffa502]' : 'text-[#00ff88]',
        isAlarm: sensor.sensorLifeStatus === 1 
      };
    }

    if (sensor.alarmState !== null && sensor.alarmState !== undefined) {
      const sosVal = String(sensor.alarmState);
      const text = ((t('deviceStatus.sos') as unknown) as Record<string, string>)[sosVal] || t('deviceStatus.sos.0');
      return { 
        key: sensor.alarmState === 1 ? 'alarm' : 'normal',
        text, 
        color: sensor.alarmState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]',
        isAlarm: sensor.alarmState === 1 
      };
    }

    if (sensor.smokeState !== null && sensor.smokeState !== undefined) {
      const smokeVal = String(sensor.smokeState);
      const text = ((t('deviceStatus.smoke') as unknown) as Record<string, string>)[smokeVal] || t('deviceStatus.smoke.0');
      return { 
        key: sensor.smokeState > 0 ? 'alarm' : 'normal',
        text, 
        color: sensor.smokeState > 0 ? 'text-[#ff4757]' : 'text-[#00ff88]',
        isAlarm: sensor.smokeState > 0 
      };
    }

    if (sensor.gasState !== null && sensor.gasState !== undefined) {
      const gasVal = String(sensor.gasState);
      const text = ((t('deviceStatus.gas') as unknown) as Record<string, string>)[gasVal] || t('deviceStatus.gas.0');
      return { 
        key: sensor.gasState > 0 ? 'alarm' : 'normal',
        text, 
        color: sensor.gasState > 0 ? 'text-[#ff4757]' : 'text-[#00ff88]',
        isAlarm: sensor.gasState > 0 
      };
    }

    if (sensor.waterState !== null && sensor.waterState !== undefined) {
      const waterVal = String(sensor.waterState);
      const text = ((t('deviceStatus.water') as unknown) as Record<string, string>)[waterVal] || t('deviceStatus.water.0');
      return { 
        key: sensor.waterState === 1 ? 'alarm' : 'normal',
        text, 
        color: sensor.waterState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
        isAlarm: sensor.waterState === 1 
      };
    }

    if (sensor.motionState !== null && sensor.motionState !== undefined) {
      const motionVal = String(sensor.motionState);
      const text = ((t('deviceStatus.motion') as unknown) as Record<string, string>)[motionVal] || t('deviceStatus.motion.0');
      return { 
        key: sensor.motionState === 1 ? 'triggered' : 'normal',
        text, 
        color: sensor.motionState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
        isAlarm: sensor.motionState === 1 
      };
    }

    if (sensor.switchState !== null && sensor.switchState !== undefined) {
      const sensorType = sensor.sensor_type?.toLowerCase() || '';
      
      if (sensorType.includes('motion') || sensorType.includes('pir')) {
        const motionVal = String(sensor.switchState);
        const text = ((t('deviceStatus.motion') as unknown) as Record<string, string>)[motionVal] || t('deviceStatus.motion.0');
        return { 
          key: sensor.switchState === 1 ? 'triggered' : 'normal',
          text, 
          color: sensor.switchState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
          isAlarm: sensor.switchState === 1 
        };
      }
      
      if (sensorType.includes('door') || sensorType.includes('contact') || sensorType.includes('window')) {
        return { 
          key: sensor.switchState === 1 ? 'open' : 'closed',
          text: sensor.switchState === 1 ? t('deviceStatus.open') : t('deviceStatus.closed'), 
          color: sensor.switchState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
          isAlarm: false 
        };
      }

      return { 
        key: sensor.switchState === 1 ? 'open' : 'closed',
        text: sensor.switchState === 1 ? t('deviceStatus.open') : t('deviceStatus.closed'), 
        color: sensor.switchState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
        isAlarm: false 
      };
    }

    const sensorType = sensor.sensor_type?.toLowerCase() || '';
    const value = parseFloat(String(sensor.value)) || 0;

    switch (sensorType) {
      case 'smoke':
        if (value > 0) {
          return { key: 'alarm', text: t('deviceStatus.smoke.1'), color: 'text-[#ff4757]', isAlarm: true };
        }
        return { key: 'normal', text: t('deviceStatus.smoke.0'), color: 'text-[#00ff88]', isAlarm: false };

      case 'co':
        if (value >= 100) {
          return { key: 'alarm', text: t('deviceStatus.gas.1'), color: 'text-[#ff4757]', isAlarm: true };
        } else if (value > 0) {
          return { key: 'warning', text: t('deviceStatus.gas.1'), color: 'text-[#ffa502]', isAlarm: false };
        }
        return { key: 'normal', text: t('deviceStatus.gas.0'), color: 'text-[#00ff88]', isAlarm: false };

      case 'water':
        if (value === 1) {
          return { key: 'alarm', text: t('deviceStatus.water.1'), color: 'text-[#00d4ff]', isAlarm: true };
        }
        return { key: 'normal', text: t('deviceStatus.water.0'), color: 'text-[#00ff88]', isAlarm: false };

      case 'contact':
      case 'door':
      case 'window':
        if (value === 1) {
          return { key: 'open', text: t('deviceStatus.open'), color: 'text-[#00d4ff]', isAlarm: false };
        }
        return { key: 'closed', text: t('deviceStatus.closed'), color: 'text-[#00ff88]', isAlarm: false };

      case 'motion':
      case 'pir':
        if (value === 1) {
          return { key: 'triggered', text: t('deviceStatus.motion.1'), color: 'text-[#00d4ff]', isAlarm: true };
        }
        return { key: 'normal', text: t('deviceStatus.motion.0'), color: 'text-[#00ff88]', isAlarm: false };

      case 'temperature':
        if (value >= 38 || value <= 0) {
          return { key: 'alarm', text: t('deviceStatus.alarm'), color: 'text-[#ff4757]', isAlarm: true };
        } else if (value >= 30 || value <= 5) {
          return { key: 'warning', text: t('deviceStatus.warning'), color: 'text-[#ffa502]', isAlarm: false };
        }
        return { key: 'normal', text: t('deviceStatus.normal'), color: 'text-[#00ff88]', isAlarm: false };

      case 'humidity':
        if (value >= 85 || value <= 20) {
          return { key: 'warning', text: t('deviceStatus.warning'), color: 'text-[#ffa502]', isAlarm: false };
        }
        return { key: 'normal', text: t('deviceStatus.normal'), color: 'text-[#00ff88]', isAlarm: false };

      case 'button':
        if (value === 1) {
          return { key: 'alarm', text: t('deviceStatus.sos.1'), color: 'text-[#ff4757]', isAlarm: true };
        }
        return { key: 'normal', text: t('deviceStatus.sos.0'), color: 'text-[#00ff88]', isAlarm: false };

      case 'siren':
        if (value === 1) {
          return { key: 'alarm', text: t('deviceStatus.alarm'), color: 'text-[#ff4757]', isAlarm: true };
        }
        return { key: 'normal', text: t('deviceStatus.normal'), color: 'text-[#00ff88]', isAlarm: false };

      case 'plug':
        if (value === 1) {
          return { key: 'open', text: t('deviceStatus.open'), color: 'text-[#00d4ff]', isAlarm: false };
        }
        return { key: 'closed', text: t('deviceStatus.closed'), color: 'text-[#00ff88]', isAlarm: false };

      case 'gateway':
        return { key: 'normal', text: t('deviceStatus.normal'), color: 'text-[#00ff88]', isAlarm: false };

      default:
        if (status === 'alarm') {
          return { key: 'alarm', text: t('deviceStatus.alarm'), color: 'text-[#ff4757]', isAlarm: true };
        }
        if (status === 'warning') {
          return { key: 'warning', text: t('deviceStatus.warning'), color: 'text-[#ffa502]', isAlarm: false };
        }
        return { key: 'normal', text: t('deviceStatus.normal'), color: 'text-[#00ff88]', isAlarm: false };
    }
  };

  const statusInfo = getStatusInfo();
  const statusStyle = statusColors[statusInfo.key] || statusColors.normal;

  return (
    <div
      className={`bg-[#0f2137] rounded-2xl p-5 border border-white/5 cursor-pointer transition-all duration-300 hover:border-[#00d4ff]/30 hover:shadow-lg hover:shadow-[#00d4ff]/10 hover:scale-[1.02] ${
        !isOnline ? 'opacity-60' : ''
      } ${statusInfo.isAlarm ? 'border-[#ff4757]/30' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`${statusStyle.bg} w-12 h-12 rounded-xl flex items-center justify-center`}>
          <Icon className={`w-6 h-6 ${statusStyle.text}`} />
        </div>
        <div className="flex items-center gap-2">
          {isOnline ? (
            <Wifi className="w-4 h-4 text-[#00ff88]" />
          ) : (
            <WifiOff className="w-4 h-4 text-[#6b7a9a]" />
          )}
          <span className={`text-xs font-medium ${statusInfo.color}`}>
            {statusInfo.text}
          </span>
          <div className={`w-2 h-2 rounded-full ${statusStyle.dot} ${statusStyle.pulse}`} />
            style.pulse}`} />

        </div>
      </div>

      <h3 className="text-lg font-semibold text-white mb-1">
        {sensor.name || t(`sensorLabels.${sensor.sensor_type}`)}
      </h3>
      <p className="text-sm text-[#6b7a9a] mb-4">
        {sensor.room_name || ''}
      </p>

      <div className="flex items-end justify-between">
        <div className="min-w-0 flex-1 pr-2">
          {(() => {
            const primary = renderPrimaryValue();
            const isStatusText = !isNumeric;
            if (isStatusText) {
              return (
                <p className={`text-lg font-semibold truncate ${statusStyle.text}`}>
                  {primary.text}
                </p>
              );
            }
            return (
              <p className={`text-2xl font-bold ${statusStyle.text}`}>
                {primary.text}
                {primary.sub && (
                  <span className="text-sm font-normal text-[#6b7a9a] ml-1">{primary.sub}</span>
                )}
              </p>
            );
          })()}
        </div>
        {statusInfo.isAlarm && (
          <AlertTriangle className="w-6 h-6 text-[#ff4757] animate-bounce shrink-0" />
        )}
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-white/5 mt-4">
        <div className="flex items-center gap-3">
          {sensor.battery !== null && sensor.battery !== undefined && sensor.battery >= 0 && (
            <BatteryIcon level={sensor.battery} isLow={isLowBattery} />
          )}
          {sensor.rssi !== null && sensor.rssi !== undefined && sensor.rssi > -999 && (
            <SignalIcon rssi={sensor.rssi} />
          )}
        </div>
        <div className="flex items-center gap-1 text-xs text-[#6b7a9a]">
          <MapPin className="w-3 h-3" />
          <span className="truncate max-w-[80px]">
            {sensor.room_name || t('noRoom')}
          </span>
        </div>
      </div>

      <p className="text-xs text-[#4a5568] mt-3">
        {t('updateTime')} {new Date(sensor.timestamp).toLocaleTimeString(i18n.language)}
      </p>
    </div>
  );
}