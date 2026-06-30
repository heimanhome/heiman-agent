import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Search, RefreshCw, ChevronDown, ChevronRight, 
  Wifi, Zap, MapPin, Battery, BatteryLow, BatteryMedium, BatteryFull,
  AlertTriangle, Thermometer, Droplets, Wind, Flame, Waves, Eye
} from 'lucide-react';
import { deviceApi, roomApi, type DeviceData, type RoomData } from '../api/client';
import { useAppStore } from '../store';

const DEFAULT_DEVICE_ICON = 'https://spapi.heiman.cn/api-saas/file/bd5cac3abfc5f6e4013a7363871d3d93.jpg?accessKey=595f278034cffdf8323097b1e04769b1';

interface RoomGroup {
  roomId: string;
  roomName: string;
  devices: DeviceData[];
  expanded: boolean;
  onlineCount: number;
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

function SensorDataItem({ icon: Icon, value, unit, label, color }: { 
  icon: any; 
  value: number | null; 
  unit: string; 
  label: string;
  color?: string;
}) {
  if (value === null || value === undefined) return null;
  
  const displayValue = typeof value === 'number' && !Number.isInteger(value) 
    ? value.toFixed(1) 
    : value;

  return (
    <div className="flex items-center gap-2">
      <Icon className={`w-3 h-3 ${color || 'text-[#6b7a9a]'}`} />
      <span className={`text-xs font-medium ${color || 'text-white'}`}>
        {displayValue}{unit}
      </span>
    </div>
  );
}

function DeviceCard({ device, t }: { device: DeviceData; t: (key: string) => string }) {
  const status = device.status?.toLowerCase() || 'offline';
  const isOffline = status === 'offline';
  const isOnline = !isOffline;
  const isLowBattery = device.battery >= 0 && device.battery <= 20;
  
  const getStatusInfo = () => {
    if (isOffline) {
      return { text: t('deviceStatus.offline'), color: 'text-[#6b7a9a]', isAlarm: false };
    }
    
    if (isLowBattery) {
      return { text: t('deviceStatus.lowBattery'), color: 'text-[#ff4757]', isAlarm: true };
    }

    if (device.tamperState !== null && device.tamperState !== undefined) {
        const tamperVal = String(device.tamperState);
        const text = ((t('deviceStatus.tamper') as unknown) as Record<string, string>)[tamperVal] || t('deviceStatus.tamper.0');
        return { 
          text, 
          color: device.tamperState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]',
          isAlarm: device.tamperState === 1 
        };
      }

      if (device.sensorLifeStatus !== null && device.sensorLifeStatus !== undefined) {
        const lifeVal = String(device.sensorLifeStatus);
        const text = ((t('deviceStatus.sensorLife') as unknown) as Record<string, string>)[lifeVal] || t('deviceStatus.sensorLife.0');
        return { 
          text, 
          color: device.sensorLifeStatus === 1 ? 'text-[#ffa502]' : 'text-[#00ff88]',
          isAlarm: device.sensorLifeStatus === 1 
        };
      }

      if (device.smokeState !== null && device.smokeState !== undefined) {
        const smokeVal = String(device.smokeState);
        const text = ((t('deviceStatus.smoke') as unknown) as Record<string, string>)[smokeVal] || t('deviceStatus.smoke.0');
        return { 
          text, 
          color: device.smokeState > 0 ? 'text-[#ff4757]' : 'text-[#00ff88]',
          isAlarm: device.smokeState > 0 
        };
      }

      if (device.gasState !== null && device.gasState !== undefined) {
        const gasVal = String(device.gasState);
        const text = ((t('deviceStatus.gas') as unknown) as Record<string, string>)[gasVal] || t('deviceStatus.gas.0');
        return { 
          text, 
          color: device.gasState > 0 ? 'text-[#ff4757]' : 'text-[#00ff88]',
          isAlarm: device.gasState > 0 
        };
      }

      if (device.waterState !== null && device.waterState !== undefined) {
        const waterVal = String(device.waterState);
        const text = ((t('deviceStatus.water') as unknown) as Record<string, string>)[waterVal] || t('deviceStatus.water.0');
        return { 
          text, 
          color: device.waterState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
          isAlarm: device.waterState === 1 
        };
      }

      if (device.switchState !== null && device.switchState !== undefined) {
        const type = device.type?.toLowerCase() || '';
        
        if (type.includes('motion') || type.includes('pir')) {
          const motionVal = String(device.switchState);
          const text = ((t('deviceStatus.motion') as unknown) as Record<string, string>)[motionVal] || t('deviceStatus.motion.0');
          return { 
            text, 
            color: device.switchState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
            isAlarm: device.switchState === 1 
          };
        }
        
        if (type.includes('door') || type.includes('contact') || type.includes('window')) {
          return { 
            text: device.switchState === 1 ? t('deviceStatus.open') : t('deviceStatus.closed'), 
            color: device.switchState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
            isAlarm: false 
          };
        }

        return { 
          text: device.switchState === 1 ? t('deviceStatus.open') : t('deviceStatus.closed'), 
          color: device.switchState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
          isAlarm: false 
        };
      }

      if (device.motionState !== null && device.motionState !== undefined) {
        const motionVal = String(device.motionState);
        const text = ((t('deviceStatus.motion') as unknown) as Record<string, string>)[motionVal] || t('deviceStatus.motion.0');
        return { 
          text, 
          color: device.motionState === 1 ? 'text-[#00d4ff]' : 'text-[#00ff88]',
          isAlarm: device.motionState === 1 
        };
      }

      if (device.alarmState !== null && device.alarmState !== undefined) {
        const sosVal = String(device.alarmState);
        const text = ((t('deviceStatus.sos') as unknown) as Record<string, string>)[sosVal] || t('deviceStatus.sos.0');
        return { 
          text, 
          color: device.alarmState === 1 ? 'text-[#ff4757]' : 'text-[#00ff88]',
          isAlarm: device.alarmState === 1 
        };
      }

    if (status === 'alarm') {
      return { text: t('deviceStatus.alarm'), color: 'text-[#ff4757]', isAlarm: true };
    }
    if (status === 'warning') {
      return { text: t('deviceStatus.warning'), color: 'text-[#ffa502]', isAlarm: true };
    }
    return { text: t('deviceStatus.normal'), color: 'text-[#00ff88]', isAlarm: false };
  };

  const statusInfo = getStatusInfo();
  const photoUrl = device.photoUrl || DEFAULT_DEVICE_ICON;

  return (
    <div
      className={`relative bg-[#0f2137] rounded-2xl p-4 border border-white/5 transition-all hover:border-[#00d4ff]/30 hover:shadow-lg hover:shadow-[#00d4ff]/5 ${
        !isOnline ? 'opacity-60' : ''
      } ${statusInfo.isAlarm ? 'border-[#ff4757]/30' : ''}`}
    >
      <div className="flex items-start gap-3 mb-3">
        <div className="relative w-14 h-14 rounded-xl overflow-hidden bg-[#0a1628] flex-shrink-0 border border-white/5">
          <img
            src={photoUrl}
            alt={device.name}
            className="w-full h-full object-contain"
            onError={(e) => {
              (e.target as HTMLImageElement).src = DEFAULT_DEVICE_ICON;
            }}
          />
          {!isOnline && (
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
              <Wifi className="w-5 h-5 text-white/60" />
            </div>
          )}
          {statusInfo.isAlarm && isOnline && (
            <div className="absolute top-1 right-1 w-3 h-3 rounded-full bg-[#ff4757] animate-pulse" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-white text-sm truncate mb-0.5">{device.name}</h3>
          <div className={`text-xs font-medium ${statusInfo.color} flex items-center gap-1`}>
            {(isLowBattery || statusInfo.isAlarm) && <AlertTriangle className="w-3 h-3" />}
            <span>{statusInfo.text}</span>
          </div>
        </div>
      </div>

      {(device.temperature !== null || device.humidity !== null || 
        device.co2 !== null || device.pm25 !== null || device.hcho !== null) && (
        <div className="flex flex-wrap gap-3 mb-3">
          <SensorDataItem 
            icon={Thermometer} 
            value={device.temperature} 
            unit="°C" 
            label="temp"
            color="text-[#ff6b6b]"
          />
          <SensorDataItem 
            icon={Droplets} 
            value={device.humidity} 
            unit="%RH" 
            label="humidity"
            color="text-[#00d4ff]"
          />
          <SensorDataItem 
            icon={Wind} 
            value={device.co2} 
            unit="ppm" 
            label="co2"
            color="text-[#ffa502]"
          />
          <SensorDataItem 
            icon={Eye} 
            value={device.pm25} 
            unit="μg/m³" 
            label="pm25"
            color="text-[#a55eea]"
          />
          <SensorDataItem 
            icon={Flame} 
            value={device.hcho} 
            unit="mg/m³" 
            label="hcho"
            color="text-[#ff4757]"
          />
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-white/5">
        <div className="flex items-center gap-3">
          {device.battery >= 0 && (
            <BatteryIcon level={device.battery} isLow={isLowBattery} />
          )}
          {device.rssi > -999 && (
            <SignalIcon rssi={device.rssi} />
          )}
        </div>
        <div className="flex items-center gap-1 text-xs text-[#6b7a9a]">
          <MapPin className="w-3 h-3" />
          <span className="truncate max-w-[100px]">
            {device.room || t('noRoom')}
          </span>
        </div>
      </div>
    </div>
  );
}

export function Devices() {
  const { t } = useTranslation('app');
  const { currentHomeId } = useAppStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [devices, setDevices] = useState<DeviceData[]>([]);
  const [rooms, setRooms] = useState<RoomData[]>([]);
  const [loading, setLoading] = useState(true);
  const [roomGroups, setRoomGroups] = useState<RoomGroup[]>([]);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const response = await deviceApi.getAll({ home_id: currentHomeId });
      const data = response.data?.data || response.data || [];
      const deviceList = Array.isArray(data) ? data : [];
      setDevices(deviceList as DeviceData[]);
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchRooms = async () => {
    try {
      const response = await roomApi.getAll(currentHomeId || undefined);
      const data = response.data?.data || response.data || [];
      const roomList = Array.isArray(data) ? data : [];
      setRooms(roomList as RoomData[]);
    } catch (error) {
      console.error('Failed to fetch rooms:', error);
      setRooms([]);
    }
  };

  useEffect(() => {
    if (currentHomeId) {
      fetchDevices();
      fetchRooms();
    }
  }, [currentHomeId]);

  useEffect(() => {
    const filtered = devices.filter(device => {
      if (!searchTerm) return true;
      const search = searchTerm.toLowerCase();
      return (device.name || '').toLowerCase().includes(search) ||
             (device.room && device.room.toLowerCase().includes(search)) ||
             (device.productName && device.productName.toLowerCase().includes(search));
    });

    const roomMap = new Map<string, RoomGroup>();
    const uncategorized: DeviceData[] = [];

    for (const device of filtered) {
      const roomKey = device.room || '';
      if (!roomKey) {
        uncategorized.push(device);
      } else {
        if (!roomMap.has(roomKey)) {
          roomMap.set(roomKey, {
            roomId: roomKey,
            roomName: roomKey,
            devices: [],
            expanded: true,
            onlineCount: 0,
          });
        }
        roomMap.get(roomKey)!.devices.push(device);
      }
    }

    const groups = Array.from(roomMap.values()).map(g => ({
      ...g,
      onlineCount: g.devices.filter(d => d.status !== 'offline').length,
    }));

    groups.sort((a, b) => a.roomName.localeCompare(b.roomName));

    if (uncategorized.length > 0) {
      groups.push({
        roomId: 'uncategorized',
        roomName: t('noRoom'),
        devices: uncategorized,
        expanded: true,
        onlineCount: uncategorized.filter(d => d.status !== 'offline').length,
      });
    }

    setRoomGroups(groups);
  }, [devices, searchTerm, t]);

  const toggleRoom = (roomId: string) => {
    setRoomGroups(groups => groups.map(g => 
      g.roomId === roomId ? { ...g, expanded: !g.expanded } : g
    ));
  };

  const handleRefresh = () => {
    fetchDevices();
    fetchRooms();
  };

  const onlineCount = devices.filter(d => d.status !== 'offline').length;
  const totalDevices = devices.length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{t('deviceManagement')}</h1>
          <p className="text-sm text-[#6b7a9a]">
            {t('manageSensors')} · {totalDevices} {t('devices')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white hover:bg-white/10 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>{t('refresh')}</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#0f2137] rounded-2xl p-5 border border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center">
              <Wifi className="w-6 h-6 text-[#0a1628]" />
            </div>
            <div>
              <p className="text-3xl font-bold text-white">{totalDevices}</p>
              <p className="text-sm text-[#6b7a9a]">{t('allDevices')}</p>
            </div>
          </div>
        </div>
        <div className="bg-[#0f2137] rounded-2xl p-5 border border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-[#00ff88]/10 flex items-center justify-center">
              <Wifi className="w-6 h-6 text-[#00ff88]" />
            </div>
            <div>
              <p className="text-3xl font-bold text-white">{onlineCount}</p>
              <p className="text-sm text-[#6b7a9a]">{t('onlineDevices')}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-[#0f2137] rounded-2xl p-4 border border-white/5">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#6b7a9a]" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={t('searchPlaceholder')}
            className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-[#6b7a9a] focus:outline-none focus:border-[#00d4ff]/50"
          />
        </div>
      </div>

      <div className="space-y-4">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-[#0f2137] rounded-2xl p-4 border border-white/5 animate-pulse h-32" />
          ))
        ) : roomGroups.length > 0 ? (
          roomGroups.map((group) => (
            <div key={group.roomId} className="bg-[#0f2137] rounded-2xl border border-white/5 overflow-hidden">
              <button
                onClick={() => toggleRoom(group.roomId)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-3">
                  {group.expanded ? (
                    <ChevronDown className="w-5 h-5 text-[#6b7a9a]" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-[#6b7a9a]" />
                  )}
                  <span className="font-semibold text-white">{group.roomName}</span>
                  <span className="text-sm text-[#6b7a9a]">
                    ({group.onlineCount}/{group.devices.length})
                  </span>
                </div>
              </button>

              {group.expanded && (
                <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {group.devices.map((device) => (
                    <DeviceCard key={device.id} device={device} t={t} />
                  ))}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="bg-[#0f2137] rounded-2xl p-12 text-center border border-white/5">
            <Zap className="w-16 h-16 text-[#6b7a9a] mx-auto mb-4" />
            <p className="text-white text-lg mb-2">{t('noData')}</p>
            <p className="text-sm text-[#6b7a9a]">{t('adjustFilter')}</p>
          </div>
        )}
      </div>
    </div>
  );
}
