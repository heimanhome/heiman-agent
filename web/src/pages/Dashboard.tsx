import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Thermometer, AlertTriangle, Wifi, Flame, Droplets, Wind, DoorOpen, Zap, Volume2, Circle, Router, Gamepad2 } from "lucide-react";
import { StatCard } from "../components/StatCard";
import { SensorCard } from "../components/SensorCard";
import { EventCard } from "../components/EventCard";
import { useAppStore } from "../store";
import { useNavigate } from "react-router-dom";

export function Dashboard() {
  const { t } = useTranslation("app");
  const { sensors, events, loading, fetchSensors, fetchEvents, fetchHomes, currentHomeId } = useAppStore();
  const navigate = useNavigate();

  useEffect(() => {
    fetchHomes();
  }, [fetchHomes]);

  useEffect(() => {
    if (currentHomeId) {
      fetchSensors();
      fetchEvents();
    }
  }, [currentHomeId, fetchSensors, fetchEvents]);

  const onlineSensors = sensors.filter((s) => s.status !== "offline");
  const alarmEvents = events.filter((e) => !e.acknowledged && (e.level === "critical" || e.level === "high"));
  const warningEvents = events.filter((e) => !e.acknowledged && (e.level === "medium" || e.level === "warning"));

  const sensorTypeIcons: Record<string, typeof Thermometer> = {
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

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{t("dashboard")}</h1>
          <p className="text-sm text-[#6b7a9a]">{t("realtimeMonitoring")}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#00ff88] animate-pulse" />
          <span className="text-sm text-[#00ff88]">{t("systemRunning")}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("onlineSensors")}
          value={onlineSensors.length}
          icon={Wifi}
          color="green"
          suffix={`/ ${sensors.length}`}
        />
        <StatCard
          title={t("activeAlarms")}
          value={alarmEvents.length}
          icon={AlertTriangle}
          color="red"
        />
        <StatCard
          title={t("warningEvents")}
          value={warningEvents.length}
          icon={Thermometer}
          color="orange"
        />
        <StatCard
          title={t("todayEvents")}
          value={events.length}
          icon={AlertTriangle}
          color="cyan"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
        <div className="lg:col-span-2 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">{t("sensorStatus")}</h2>
            <button
              onClick={() => navigate("/sensors")}
              className="text-sm text-[#00d4ff] hover:underline"
            >
              {t("viewAll")}
            </button>
          </div>
          <div className="flex-1">
            {loading.sensors ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="bg-[#0f2137] rounded-2xl p-5 border border-white/5 animate-pulse" />
                ))}
              </div>
            ) : sensors.length === 0 ? (
              <div className="bg-[#0f2137] rounded-2xl p-12 text-center border border-white/5">
                <Wifi className="w-12 h-12 text-[#6b7a9a] mx-auto mb-4" />
                <p className="text-white mb-2">{t("noSensorData")}</p>
                <p className="text-sm text-[#6b7a9a]">{t("checkDeviceConnection")}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sensors.slice(0, 4).map((sensor) => (
                  <SensorCard
                    key={sensor.did}
                    sensor={sensor}
                    onClick={() => navigate(`/sensors/${sensor.did}`)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">{t("recentEvents")}</h2>
            <button
              onClick={() => navigate("/events")}
              className="text-sm text-[#00d4ff] hover:underline"
            >
              {t("viewAll")}
            </button>
          </div>
          <div className="flex-1">
            {loading.events ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-[#0f2137] rounded-xl p-4 border border-white/5 animate-pulse" />
                ))}
              </div>
            ) : events.length === 0 ? (
              <div className="bg-[#0f2137] rounded-xl p-12 text-center border border-white/5">
                <AlertTriangle className="w-12 h-12 text-[#6b7a9a] mx-auto mb-4" />
                <p className="text-white mb-2">{t("noEventRecords")}</p>
                <p className="text-sm text-[#6b7a9a]">{t("systemNormal")}</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {events.slice(0, 5).map((event) => (
                  <EventCard
                    key={event.event_id}
                    event={event}
                    onAcknowledge={() => useAppStore.getState().acknowledgeEvent(event.event_id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
