import { useTranslation } from 'react-i18next';
import { AlertCircle, AlertTriangle, Info, CheckCircle } from 'lucide-react';
import type { SensorEvent } from '../types';

interface EventCardProps {
  event: SensorEvent;
  onAcknowledge?: () => void;
}

const eventIcons = {
  alarm: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const levelColors = {
  critical: {
    dot: 'bg-[#ff4757]',
    text: 'text-[#ff4757]',
    bg: 'bg-[#ff4757]/10',
  },
  high: {
    dot: 'bg-[#ff6b6b]',
    text: 'text-[#ff6b6b]',
    bg: 'bg-[#ff6b6b]/10',
  },
  medium: {
    dot: 'bg-[#ffa502]',
    text: 'text-[#ffa502]',
    bg: 'bg-[#ffa502]/10',
  },
  low: {
    dot: 'bg-[#00d4ff]',
    text: 'text-[#00d4ff]',
    bg: 'bg-[#00d4ff]/10',
  },
  warning: {
    dot: 'bg-[#ffa502]',
    text: 'text-[#ffa502]',
    bg: 'bg-[#ffa502]/10',
  },
  info: {
    dot: 'bg-[#00d4ff]',
    text: 'text-[#00d4ff]',
    bg: 'bg-[#00d4ff]/10',
  },
};

export function EventCard({ event, onAcknowledge }: EventCardProps) {
  const { t, i18n } = useTranslation('app');
  const eventTypeKey = event.event_type || 'info';
  const levelKey = event.level || 'low';
  const Icon = eventIcons[eventTypeKey as keyof typeof eventIcons] || eventIcons.info;
  const level = levelColors[levelKey as keyof typeof levelColors] || levelColors.low;

  return (
    <div
      className={`bg-[#0f2137] rounded-xl p-4 border border-white/5 transition-all duration-300 ${
        event.acknowledged
          ? 'opacity-60'
          : 'hover:border-[#00d4ff]/30 hover:shadow-lg hover:shadow-[#00d4ff]/10'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className={`${level.bg} w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0`}>
            <Icon className={`w-5 h-5 ${level.text}`} />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${level.bg} ${level.text}`}>
                {t(`eventLevelLabels.${event.level}`)}
              </span>
              <span className="text-xs text-[#6b7a9a]">{t(`sensorLabels.${event.sensor_type}`) || event.sensor_type}</span>
              {event.acknowledged && (
                <span className="text-xs text-[#00ff88] flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" />
                  {t('acknowledged')}
                </span>
              )}
            </div>
            <p className="text-sm text-white font-medium">{event.message}</p>
            <p className="text-xs text-[#4a5568] mt-1">{t('device')}: {event.device_name || event.did}</p>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-xs text-[#6b7a9a]">
            {new Date(event.timestamp).toLocaleString(i18n.language)}
          </p>
          {!event.acknowledged && onAcknowledge && (
            <button
              onClick={onAcknowledge}
              className="mt-2 px-3 py-1 text-xs font-medium text-[#00d4ff] bg-[#00d4ff]/10 rounded-lg hover:bg-[#00d4ff]/20 transition-colors"
            >
              {t('acknowledge')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
