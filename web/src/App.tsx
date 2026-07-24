import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom';
import { Sidebar, MobileTabBar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { Dashboard } from './pages/Dashboard';
import { Events } from './pages/Events';
import { Rules } from './pages/Rules';
import { RuleEditor } from './pages/RuleEditor';
import { Homes } from './pages/Homes';
import { Logs } from './pages/Logs';
import { Models } from './pages/Models';
import { Devices } from './pages/Devices';
import { DeviceDetail } from './pages/DeviceDetail';
import { Persons } from './pages/Persons';
import { Tasks } from './pages/Tasks';
import { Observability } from './pages/Observability';
import { SelfLearning } from './pages/SelfLearning';
import { Login } from './pages/Login';
import { AuthGuard } from './components/AuthGuard';
import { ToastHost } from './components/Toast';
import { useTheme } from './hooks/useTheme';
import { useSSE } from './hooks/useSSE';
import { useAppStore } from './store';

function AppLayout() {
  const updateSensor = useAppStore((state) => state.updateSensor);
  const fetchEvents = useAppStore((state) => state.fetchEvents);

  useSSE({
    enabled: true,
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
        <Route path="/login" element={<Login />} />
        <Route element={<AuthGuard><AppLayout /></AuthGuard>}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/homes" element={<Homes />} />
          <Route path="/events" element={<Events />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="/rules/new" element={<RuleEditor />} />
          <Route path="/rules/:rule_id" element={<RuleEditor />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/models" element={<Models />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="/devices/:deviceId" element={<DeviceDetail />} />
          <Route path="/persons" element={<Persons />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/observability" element={<Observability />} />
          <Route path="/self-learning" element={<SelfLearning />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
