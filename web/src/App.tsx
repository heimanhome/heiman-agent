import { BrowserRouter, Routes, Route, Outlet, Navigate } from 'react-router-dom';
import { Sidebar, MobileTabBar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { Dashboard } from './pages/Dashboard';
import { Sensors } from './pages/Sensors';
import { SensorDetail } from './pages/SensorDetail';
import { Events } from './pages/Events';
import { Rules } from './pages/Rules';
import { RuleEditor } from './pages/RuleEditor';
import { Homes } from './pages/Homes';
import { Logs } from './pages/Logs';
import { Models } from './pages/Models';
import { Devices } from './pages/Devices';
import { Persons } from './pages/Persons';
import { Tasks } from './pages/Tasks';
import { Observability } from './pages/Observability';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { AuthGuard } from './components/AuthGuard';
import { ToastHost } from './components/Toast';
import { useTheme } from './hooks/useTheme';
import { useSSE } from './hooks/useSSE';
import { useAppStore } from './store';
import { authManager } from './api/auth-manager';

function AppLayout() {
  const updateSensor = useAppStore((state) => state.updateSensor);
  const fetchEvents = useAppStore((state) => state.fetchEvents);

  useSSE({
    enabled: authManager.isAuthenticated(),
    onDeviceUpdate: (deviceId, properties) => {
      updateSensor(deviceId, properties);
    },
    onDeviceEvent: (deviceId, eventType, payload) => {
      console.log('[SSE] Device event received:', deviceId, eventType, payload);
      fetchEvents(true);
    },
  });

  return (
    <div className="h-screen flex overflow-hidden bg-gray-50 dark:bg-[#0f172a]">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <TopBar />
        <main className="flex-1 overflow-y-auto min-h-0">
          <Outlet />
        </main>
        <div className="md:hidden shrink-0">
          <MobileTabBar />
        </div>
      </div>
      <ToastHost />
    </div>
  );
}

function App() {
  const { effective } = useTheme();

  return (
    <BrowserRouter>
      <Routes>
        {/* 兼容旧路径 /auth/login，重定向到 /login */}
        <Route path="/auth/login" element={<Navigate to="/login" replace />} />
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route element={<AuthGuard><AppLayout /></AuthGuard>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/homes" element={<Homes />} />
          <Route path="/sensors" element={<Sensors />} />
          <Route path="/sensors/:did" element={<SensorDetail />} />
          <Route path="/events" element={<Events />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="/rules/new" element={<RuleEditor />} />
          <Route path="/rules/:rule_id" element={<RuleEditor />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/models" element={<Models />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="/persons" element={<Persons />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/observability" element={<Observability />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
