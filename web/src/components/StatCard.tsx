import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: number;
  icon: LucideIcon;
  color: 'cyan' | 'green' | 'red' | 'orange';
  suffix?: string;
}

const colorClasses = {
  cyan: {
    bg: 'bg-[#00d4ff]/10',
    iconBg: 'bg-[#00d4ff]/20',
    iconColor: 'text-[#00d4ff]',
    textColor: 'text-[#00d4ff]',
    glow: 'shadow-lg shadow-[#00d4ff]/20',
  },
  green: {
    bg: 'bg-[#00ff88]/10',
    iconBg: 'bg-[#00ff88]/20',
    iconColor: 'text-[#00ff88]',
    textColor: 'text-[#00ff88]',
    glow: 'shadow-lg shadow-[#00ff88]/20',
  },
  red: {
    bg: 'bg-[#ff4757]/10',
    iconBg: 'bg-[#ff4757]/20',
    iconColor: 'text-[#ff4757]',
    textColor: 'text-[#ff4757]',
    glow: 'shadow-lg shadow-[#ff4757]/20',
  },
  orange: {
    bg: 'bg-[#ffa502]/10',
    iconBg: 'bg-[#ffa502]/20',
    iconColor: 'text-[#ffa502]',
    textColor: 'text-[#ffa502]',
    glow: 'shadow-lg shadow-[#ffa502]/20',
  },
};

export function StatCard({ title, value, icon: Icon, color, suffix = '' }: StatCardProps) {
  const classes = colorClasses[color];

  return (
    <div className={`${classes.bg} rounded-2xl p-6 border border-white/5 transition-all duration-500 hover:${classes.glow} hover:scale-[1.02]`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-[#6b7a9a] mb-2">{title}</p>
          <p className={`text-3xl font-bold ${classes.textColor}`}>
            {value}
            <span className="text-lg font-normal text-[#6b7a9a] ml-1">{suffix}</span>
          </p>
        </div>
        <div className={`${classes.iconBg} w-12 h-12 rounded-xl flex items-center justify-center`}>
          <Icon className={`w-6 h-6 ${classes.iconColor}`} />
        </div>
      </div>
    </div>
  );
}
