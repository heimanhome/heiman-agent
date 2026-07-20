import { useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Thermometer,
  AlertTriangle,
  Settings,
  Flame,
  Home,
  FileText,
  Cpu,
  Activity,
  Users,
  CheckSquare,
  BarChart3,
} from 'lucide-react';
import { AccountButton } from './AccountButton';
import { useAppStore } from '../store';

export type TabKey =
  | "dashboard"
  | "sensors"
  | "events"
  | "rules"
  | "homes"
  | "logs"
  | "models"
  | "devices"
  | "persons"
  | "tasks"
  | "observability";

const navItems: { icon: typeof LayoutDashboard; path: string; menuKey: TabKey; tabKey: TabKey }[] = [
  { icon: LayoutDashboard, path: "/", menuKey: "dashboard", tabKey: "dashboard" },
  { icon: Home, path: "/homes", menuKey: "homes", tabKey: "homes" },
  { icon: Activity, path: "/devices", menuKey: "devices", tabKey: "devices" },
  { icon: Thermometer, path: "/sensors", menuKey: "sensors", tabKey: "sensors" },
  { icon: AlertTriangle, path: "/events", menuKey: "events", tabKey: "events" },
  { icon: CheckSquare, path: "/tasks", menuKey: "tasks", tabKey: "tasks" },
  { icon: Users, path: "/persons", menuKey: "persons", tabKey: "persons" },
  { icon: FileText, path: "/logs", menuKey: "logs", tabKey: "logs" },
  { icon: Cpu, path: "/models", menuKey: "models", tabKey: "models" },
  { icon: BarChart3, path: "/observability", menuKey: "observability", tabKey: "observability" },
  { icon: Settings, path: "/rules", menuKey: "rules", tabKey: "rules" },
];

export function Sidebar() {
  const { t } = useTranslation("app");
  const navigate = useNavigate();
  const { profile, fetchProfile } = useAppStore();
  const username = profile?.nickName || profile?.username || '';
  
  const accountBtnRef = useRef<HTMLButtonElement>(null);
  const accountRowRef = useRef<HTMLDivElement>(null);

  const token = localStorage.getItem('heiman_access_token');
  const isBound = !!token;

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleBind = () => {
    window.location.href = '/api/auth/login';
  };

  const handleChanged = () => {
    window.location.reload();
  };

  return (
    <>
      <aside
        className="hidden md:flex flex-col shrink-0 border-r border-gray-200 dark:border-[#1e3a5f] bg-white dark:bg-white dark:bg-[#0a1628] w-[15%] min-w-[172px]"
      >
        <header
          className="flex items-center gap-2.5 shrink-0 border-b border-gray-200 dark:border-[#1e3a5f]"
          style={{ minHeight: 64, paddingLeft: 18, paddingRight: 18 }}
        >
          <div className="w-7 h-7 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
            <Flame className="w-4 h-4 text-gray-700 dark:text-gray-300" />
          </div>
          <span className="text-title text-gray-900 dark:text-gray-100">Heiman</span>
        </header>

        <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `w-full flex items-center rounded-lg transition-colors text-left gap-3 px-3 py-3 ${
                  isActive
                    ? "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    : "text-gray-600 dark:text-[#6b7a9a] hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:text-gray-900 dark:hover:text-gray-200"
                }`
              }
            >
              <item.icon className="w-5 h-5 shrink-0" />
              <div className="flex flex-col min-w-0 leading-tight">
                <span className="text-sm font-semibold">{t(`menu.${item.menuKey}.title`)}</span>
                <span className="text-xs opacity-60 mt-0.5">{t(`menu.${item.menuKey}.subtitle`)}</span>
              </div>
            </NavLink>
          ))}
        </nav>

        <div
          ref={accountRowRef}
          className="px-3 py-3 border-t border-gray-200 dark:border-[#1e3a5f] flex items-center gap-2 cursor-pointer hover:bg-white/5 transition-colors"
          onClick={(e) => {
            const target = e.target as HTMLElement;
            if (target.closest("button") || target.closest('[role="menu"]')) return;
            accountBtnRef.current?.click();
          }}
        >
          <AccountButton
            ref={accountBtnRef}
            anchorWrapperRef={accountRowRef}
            bound={isBound}
            accountName={username || t('account.name')}
            onBind={handleBind}
            onChanged={handleChanged}
            popoverPlacement="top"
          />
          <div className="min-w-0 flex-1">
            {isBound ? (
              <>
                <div className="text-sm text-white truncate">
                  {username || t('account.name')}
                </div>
              </>
            ) : (
              <div className="text-xs text-[#6b7a9a] truncate">
                {t('bindAccount')}
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

export function MobileTabBar() {
  const { t } = useTranslation("app");

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white dark:bg-[#0a1628] border-t border-gray-200 dark:border-[#1e3a5f] md:hidden">
      <div className="flex items-center justify-around p-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 px-4 py-2 rounded-xl transition-colors ${
                isActive
                  ? "text-gray-900 dark:text-gray-100"
                  : "text-gray-500 dark:text-[#6b7a9a]"
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            <span className="text-xs">{t(`menu.${item.menuKey}.title`)}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
