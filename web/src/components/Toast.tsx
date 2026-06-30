import { useEffect, useState, useCallback } from "react";
import { CheckCircle, AlertCircle, XCircle, X } from "lucide-react";

export type ToastTone = "ok" | "warn" | "error";

interface Toast {
  id: string;
  text: string;
  tone: ToastTone;
}

const TONE_CONFIG = {
  ok: {
    icon: CheckCircle,
    bg: "bg-green-500/10",
    border: "border-green-500/30",
    text: "text-green-400",
    iconColor: "text-green-400",
  },
  warn: {
    icon: AlertCircle,
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    text: "text-amber-400",
    iconColor: "text-amber-400",
  },
  error: {
    icon: XCircle,
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    text: "text-red-400",
    iconColor: "text-red-400",
  },
};

const TOAST_LIFETIME_MS = 4000;

let toastIdCounter = 0;
let queue: Toast[] = [];

export function toast(text: string, tone: ToastTone = "ok") {
  const id = String(++toastIdCounter);
  queue = [...queue, { id, text, tone }];
  notifyListeners();
}

type Listener = () => void;
const listeners: Listener[] = [];

function notifyListeners() {
  listeners.forEach((l) => l());
}

function subscribe(listener: Listener) {
  listeners.push(listener);
  return () => {
    const idx = listeners.indexOf(listener);
    if (idx >= 0) listeners.splice(idx, 1);
  };
}

export function dismissToast(id: string) {
  queue = queue.filter((t) => t.id !== id);
  notifyListeners();
}

export function ToastHost() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const unsubscribe = subscribe(() => setToasts([...queue]));
    return unsubscribe;
  }, []);

  useEffect(() => {
    const timers = toasts.map((t) =>
      setTimeout(() => dismissToast(t.id), TOAST_LIFETIME_MS)
    );
    return () => timers.forEach(clearTimeout);
  }, [toasts]);

  const handleRemove = useCallback((id: string) => {
    dismissToast(id);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => {
        const config = TONE_CONFIG[t.tone];
        const Icon = config.icon;
        return (
          <div
            key={t.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg backdrop-blur-sm ${config.bg} ${config.border} animate-fadeIn`}
          >
            <Icon className={`w-5 h-5 shrink-0 ${config.iconColor}`} />
            <span className={`text-sm ${config.text}`}>{t.text}</span>
            <button
              type="button"
              onClick={() => handleRemove(t.id)}
              className="p-1 rounded hover:bg-white/10 transition-colors"
            >
              <X className="w-4 h-4 text-white/60" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export { toast as default };
