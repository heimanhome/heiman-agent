import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { deviceApi, authApi, roomApi } from '../api/client';
import { useAppStore } from '../store';

interface PanelSession {
  entryUrl: string;
  revoke: () => void;
  fileCount: number;
  sessionId: string;
}

interface DeviceMeta {
  id: string;
  name: string;
  deviceName?: string;
  productId: string;
  productName: string;
  deviceType: string;
  homeId: string;
  homeName?: string;
  roomId: string;
  roomName: string;
  status: string;
  properties: Record<string, any>;
  photoUrl: string;
  mesSn?: string;
  isShareDevice?: boolean;
  isGateway?: boolean;
  is4GDevice?: boolean;
  isNBDevice?: boolean;
  parentId?: string;
  roomSort?: number;
  sort?: number;
  mac?: string;
}

interface ProfileInfo {
  userId?: string;
  id?: string;
  nickname?: string;
  nickName?: string;
  username?: string;
  accessToken?: string;
}

interface RawDeviceData {
  id?: string;
  name?: string;
  deviceName?: string;
  productId?: string;
  productName?: string;
  type?: string;
  home_id?: string;
  homeId?: string;
  homeName?: string;
  room?: string;
  roomId?: string;
  roomName?: string;
  status?: string;
  online?: boolean;
  state?: { value?: string };
  deriveMetadata?: string | Array<{ property?: string; value?: any; name?: string }>;
  photoUrl?: string;
  mesSn?: string;
  sn?: string;
  mac?: string;
  isShareDevice?: boolean;
  isGateway?: boolean;
  is4GDevice?: boolean;
  isNBDevice?: boolean;
  parentId?: string;
  roomSort?: number;
  sort?: number;
  properties?: Record<string, any>;
  deviceType?: { value?: string } | string;
}

// Must match the type sent by the backend-injected bridge JS and Vue reference project webDsBridge.js
const MSG_SOURCE = 'dsbridge-call';
const RESULT_TYPE = 'dsbridge-result';

function parseParams(params: any): any {
  if (params == null || params === '') return {};
  if (typeof params === 'string') {
    try {
      return JSON.parse(params);
    } catch {
      return params;
    }
  }
  return params;
}

export function DeviceDetail() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();
  const { currentHomeId } = useAppStore();
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [iframeSrc, setIframeSrc] = useState('');
  const [deviceName, setDeviceName] = useState('');
  
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const panelSessionRef = useRef<PanelSession | null>(null);
  const disposedRef = useRef(false);
  const deviceMetaRef = useRef<DeviceMeta | null>(null);
  const profileRef = useRef<ProfileInfo | null>(null);
  const homeIdRef = useRef(currentHomeId);
  homeIdRef.current = currentHomeId;
  const deviceIdRef = useRef(deviceId);
  deviceIdRef.current = deviceId;

  // ---------- Bridge: helper to get home name from store ----------

  const getHomeName = (): string => {
    const state = useAppStore.getState();
    // Prefer currentHomeId from store, fall back to device's homeId
    let hid = homeIdRef.current || state.currentHomeId;
    if (!hid) hid = deviceMetaRef.current?.homeId || '';
    if (!hid) return '';
    const home = state.homes.find(h => h.id === hid);
    return home?.name || '';
  };

  // ---------- Bridge: data builders (ref-based to avoid stale closures) ----------

  const buildDeviceInfo = (): Record<string, any> => {
    const d = deviceMetaRef.current || {
      id: '',
      name: '',
      productId: '',
      productName: '',
      deviceType: '',
      homeId: '',
      roomId: '',
      roomName: '',
      status: '',
      properties: {},
      photoUrl: '',
    };
    const hid = d.homeId || homeIdRef.current || '';
    return {
      photoUrl: d.photoUrl || '',
      deviceName: d.deviceName || d.name || deviceName || '',
      deviceType: d.deviceType || '',
      homeId: hid,
      homeName: d.homeName || getHomeName(),
      id: d.id || deviceIdRef.current || '',
      mesSn: d.mesSn || '',
      isShareDevice: !!d.isShareDevice,
      isGateway: !!(d.isGateway || d.deviceType === 'gateway'),
      is4GDevice: !!d.is4GDevice,
      isNBDevice: !!d.isNBDevice,
      name: d.name || d.mac || '',
      parentId: d.parentId || '',
      productId: d.productId || '',
      productName: d.productName || '',
      roomId: d.roomId || '',
      roomName: d.roomName || '',
      roomSort: d.roomSort ?? 0,
      sort: d.sort ?? 0,
      status: d.status === 'online' ? 1 : 0,
      properties: d.properties || {},
    };
  };

  const buildPhoneInfo = (): Record<string, any> => {
    const el = iframeRef.current;
    const screenW = el?.clientWidth || window.innerWidth || 1280;
    const screenH = el?.clientHeight || window.innerHeight || 800;
    return {
      statusBarH: 0,
      navBarHeight: 48,
      screenW,
      screenH,
      safeArea: 0,
      isDarkMode: document.documentElement.getAttribute('data-theme') === 'dark',
      phoneType: 'web',
      version: 'web-preview',
    };
  };

  const buildUserInfoSync = (): Record<string, any> => {
    const p = profileRef.current || {};
    return {
      accountId: p.userId || p.id || '',
      accountToken: p.accessToken || '',
      appId: import.meta.env.VITE_APP_ID || '11',
      tempType: 0,
      countryCode: '86',
      nickName: p.nickname || p.nickName || p.username || '',
      homeId: homeIdRef.current || '',
      homeName: getHomeName(),
      isEnableDebug: false,
      timezoneValue: 'GMT+08:00',
      olsonId: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai',
      isRootUser: true,
      is12HourFormat: false,
    };
  };

  // ---------- Bridge: jsHttpsRequest proxy (forward panel API calls with auth) ----------

  const API_BASE_URLS: Record<string, string> = {
    test: 'http://192.168.1.14:9900',
    cn: 'https://api.heiman.cn',
    eu: 'https://spapi.heiman.cn',
  };

  const handleJsHttpsRequest = async (rawParams: any, callbackId: string) => {
    const params = parseParams(rawParams) || {};
    const method = String(params.method || 'post').toLowerCase();
    let url = String(params.url || '');
    if (!url) {
      reply(callbackId, JSON.stringify({ status: 400, message: 'missing url', result: null }));
      return;
    }

    // If relative URL, prefix with API base (matching Vue behavior)
    if (!/^https?:\/\//i.test(url)) {
      const region = import.meta.env.VITE_API_REGION || 'test';
      const base = API_BASE_URLS[region] || API_BASE_URLS.test;
      url = `${base.replace(/\/$/, '')}/${url.replace(/^\//, '')}`;
    }

    try {
      const token = profileRef.current?.accessToken || '';
      const res = await axios({
        method,
        url,
        data: method === 'get' ? undefined : params.params,
        params: method === 'get' ? params.params : undefined,
        headers: {
          'Content-Type': 'application/json',
          'tenant-id': '1',
          ...(token ? { Authorization: `bearer ${token}` } : {}),
        },
        timeout: 30000,
      });
      reply(callbackId, JSON.stringify(res.data ?? {}));
    } catch (err: any) {
      const status = err.response?.status || 500;
      const body = err.response?.data;
      reply(
        callbackId,
        JSON.stringify(
          body && typeof body === 'object'
            ? body
            : { status, message: err.message || 'request failed', result: null }
        )
      );
    }
  };

  // ---------- Bridge: postMessage reply ----------

  const sendToIframe = (payload: any) => {
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    try {
      win.postMessage(payload, '*');
    } catch (err) {
      console.warn('[WebDsBridge] postMessage failed', err);
    }
  };

  const reply = (callbackId: string | undefined, data: any) => {
    if (!callbackId) return;
    sendToIframe({
      type: RESULT_TYPE,
      callbackId,
      result: data,
    });
  };

  // ---------- Bridge: dispatch handler (plain function, no re-render triggers) ----------

  const dispatch = async (method: string, rawParams: any, callbackId: string) => {
    const params = parseParams(rawParams);

    switch (method) {
      case 'getDeviceInfo':
        reply(callbackId, buildDeviceInfo());
        return;
      case 'getUserInfo': {
        // If profile not loaded yet, fetch it first before replying
        if (!profileRef.current.userId && !profileRef.current.id) {
          try {
            const res = await authApi.getProfile();
            if (res.data?.success && res.data?.data) {
              profileRef.current = res.data.data as ProfileInfo;
            }
          } catch { /* ignore */ }
        }
        reply(callbackId, buildUserInfoSync());

        // Refresh profile for next calls
        try {
          const res = await authApi.getProfile();
          if (res.data?.success && res.data?.data) {
            profileRef.current = res.data.data as ProfileInfo;
          }
        } catch { /* ignore */ }
        return;
      }
      case 'getPhoneInfo':
        reply(callbackId, buildPhoneInfo());
        return;
      case 'getLanguage':
        reply(callbackId, 'zh-CN');
        return;
      case 'getAppType':
        reply(callbackId, '0');
        return;
      case 'backToApp':
        handleBack();
        reply(callbackId, null);
        return;
      case 'showToast': {
        const text = typeof params === 'string' ? params : params?.message || params?.title || '';
        if (text) alert(text);
        reply(callbackId, null);
        return;
      }
      case 'showLoadingToast': {
        const text = typeof params === 'string' ? params : params?.message || '加载中...';
        console.log('[WebDsBridge] loading:', text);
        reply(callbackId, null);
        return;
      }
      case 'hideToast':
        reply(callbackId, null);
        return;
      case 'showAlert': {
        const cfg = typeof params === 'object' && params ? params : { message: String(params || '') };
        const confirmed = window.confirm(cfg.message || '');
        reply(callbackId, confirmed);
        return;
      }
      case 'jsHttpsRequest':
        await handleJsHttpsRequest(params, callbackId);
        return;
      case 'readDeviceProperties': {
        const props = deviceMetaRef.current.properties || {};
        if (Array.isArray(params) && params.length > 0) {
          const result: Record<string, any> = {};
          params.forEach((key: string) => {
            if (key in props) result[key] = props[key];
          });
          reply(callbackId, result);
        } else if (typeof params === 'string' && params) {
          reply(callbackId, params in props ? { [params]: props[params] } : {});
        } else {
          reply(callbackId, props);
        }
        return;
      }
      case 'setDeviceProperties': {
        if (Array.isArray(params)) {
          params.forEach((item: any) => {
            const key = item?.property || item?.name || item?.key;
            const value = item?.value;
            if (key !== undefined) {
              deviceMetaRef.current.properties[key] = value;
              deviceApi.control(deviceId!, key, value).catch((err) => {
                console.warn('[WebDsBridge] setDeviceProperties control failed:', key, err);
              });
            }
          });
        } else if (params && typeof params === 'object') {
          Object.entries(params).forEach(([key, value]) => {
            deviceMetaRef.current.properties[key] = value;
            deviceApi.control(deviceId!, key, value).catch((err) => {
              console.warn('[WebDsBridge] setDeviceProperties control failed:', key, err);
            });
          });
        }
        reply(callbackId, 'success');
        return;
      }
      case 'setDeviceFunctions': {
        if (Array.isArray(params)) {
          params.forEach((item: any) => {
            const key = item?.functionId || item?.identifier || item?.name || item?.key;
            const value = item?.value;
            if (key !== undefined) {
              deviceApi.control(deviceId!, key, value).catch((err) => {
                console.warn('[WebDsBridge] setDeviceFunctions control failed:', key, err);
              });
            }
          });
        } else if (params && typeof params === 'object') {
          Object.entries(params).forEach(([key, value]) => {
            deviceApi.control(deviceId!, key, value).catch((err) => {
              console.warn('[WebDsBridge] setDeviceFunctions control failed:', key, err);
            });
          });
        }
        reply(callbackId, 'success');
        return;
      }
      case 'getDeviceProperty':
        reply(callbackId, buildDeviceInfo()?.properties || {});
        return;
      case 'getRoomList': {
        try {
          const hid = params?.homeId || homeIdRef.current;
          const res = await roomApi.getAll(hid || undefined);
          const rooms = res.data?.success ? res.data.data || [] : [];
          reply(callbackId, rooms);
        } catch {
          reply(callbackId, []);
        }
        return;
      }
      case 'setStatusBarType':
      case 'updateDevice':
      case 'updateHome':
      case 'copyStringInfo':
        reply(callbackId, null);
        return;
      case 'isSupportDesktopShortcut':
      case 'isSupportSiriShortcut':
        reply(callbackId, false);
        return;
      case 'shareDevice':
      case 'otaDevice':
      case 'feedbackDevice':
      case 'reconnect':
      case 'jumpToSubDevice':
      case 'jumpToAddSubDevice':
      case 'createDesktopShortcut':
      case 'createSiriShortcut':
      case 'scanBluetoothDevice':
      case 'scanAndConnectBluetoothDevices':
      case 'bluetoothWriteData':
      case 'getBluetoothStatus':
      case 'getBluetoothPermission':
      case 'setBluetoothMtuSize':
      case 'parsingBluetoothServices':
      case 'setSubDeviceProperties':
      case 'setDeviceReset':
      case 'deleteDeviceSuccess':
      case 'openMapNavigation':
      case 'getCurrentLocation':
      case 'fetchRemoteText':
      case 'fetchRemoteImageBase64':
      case 'showActionSheet':
      case 'showTextInput':
      case 'getDevicesPhotoUrl':
        reply(callbackId, method.startsWith('isSupport') ? false : null);
        return;
      case '_dsb.dsinit':
        // DSBridge init handshake: tell panel the bridge is ready
        reply(callbackId, true);
        return;
      default:
        console.warn('[WebDsBridge] unhandled method:', method);
        reply(callbackId, null);
    }
  };

  // ---------- Bridge: stable message listener (registered once) ----------

  const dispatchRef = useRef(dispatch);
  dispatchRef.current = dispatch;

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (disposedRef.current) return;
      const msg = event.data;
      if (!msg || msg.type !== MSG_SOURCE || !msg.method) return;

      const iframe = iframeRef.current;
      if (iframe?.contentWindow && event.source && event.source !== iframe.contentWindow) {
        return;
      }

      dispatchRef.current(msg.method, msg.params, msg.callbackId);
    };

    window.addEventListener('message', handler);

    return () => {
      window.removeEventListener('message', handler);
      disposedRef.current = true;
      panelSessionRef.current?.revoke();
      panelSessionRef.current = null;
    };
  }, []); // Register once, uses dispatchRef to always get latest handler

  // ---------- Navigation ----------

  const handleBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/devices');
    }
  }, [navigate]);

  // ---------- Panel loading ----------

  const loadPanel = useCallback(async () => {
    if (!deviceId) return;

    setLoading(true);
    setError('');
    setIframeSrc('');
    panelSessionRef.current?.revoke();
    panelSessionRef.current = null;

    try {
      // 1. Fetch device meta
      const response = await deviceApi.getById(deviceId);
      const raw = response.data?.data as RawDeviceData || response.data as RawDeviceData || {};
      
      let properties: Record<string, any> = {};
      if (raw.deriveMetadata) {
        try {
          const metadata = typeof raw.deriveMetadata === 'string'
            ? JSON.parse(raw.deriveMetadata)
            : raw.deriveMetadata;
          if (Array.isArray(metadata)) {
            metadata.forEach((item: any) => {
              const key = item.property || item.name;
              if (key && item.value !== undefined) {
                properties[key] = item.value;
              }
            });
          }
        } catch (e) {
          console.warn('解析设备元数据失败:', e);
        }
      }

      if (raw.properties && typeof raw.properties === 'object') {
        properties = { ...properties, ...raw.properties };
      }

      const meta: DeviceMeta = {
        id: raw.id || deviceId,
        name: raw.name || raw.deviceName || '设备面板',
        deviceName: raw.deviceName || raw.name || '',
        productId: raw.productId || '',
        productName: raw.productName || '',
        deviceType: typeof raw.deviceType === 'object' ? (raw.deviceType as any).value : (raw.type || raw.deviceType as string || ''),
        homeId: raw.homeId || raw.home_id || currentHomeId || '',
        homeName: raw.homeName || '',
        roomId: raw.roomId || raw.room || '',
        roomName: raw.roomName || raw.room || '',
        status: raw.status || '',
        properties,
        photoUrl: raw.photoUrl || '',
        mesSn: raw.mesSn || raw.sn || '',
        isShareDevice: raw.isShareDevice,
        isGateway: raw.isGateway || (typeof raw.deviceType === 'object' ? (raw.deviceType as any).value : raw.deviceType as string || '') === 'gateway',
        is4GDevice: raw.is4GDevice,
        isNBDevice: raw.isNBDevice,
        parentId: raw.parentId,
        roomSort: raw.roomSort,
        sort: raw.sort,
        mac: raw.mac,
      };

      deviceMetaRef.current = meta;
      setDeviceName(meta.name);

      if (!meta.productId) {
        throw new Error('设备缺少 productId，无法加载面板');
      }

      // 2. Fetch panel from backend
      console.log('[DevicePanel] fetching panel from backend');
      const panelResponse = await deviceApi.getPanel(deviceId, currentHomeId);

      if (!panelResponse.data.success) {
        throw new Error(panelResponse.data.message || '获取面板信息失败');
      }

      const panelData = panelResponse.data.data;
      const panelUrl = panelData.panelUrl;
      console.log('[DevicePanel] panelUrl:', panelUrl);

      // 3. Fetch profile (required for panel to authenticate with real token)
      //    Also ensure homes are loaded for homeName resolution
      try {
        const [profileRes] = await Promise.all([
          authApi.getProfile(),
          (async () => {
            const state = useAppStore.getState();
            if (state.homes.length === 0) {
              await state.fetchHomes();
            }
          })(),
        ]);
        if (profileRes.data?.success && profileRes.data?.data) {
          profileRef.current = profileRes.data.data as ProfileInfo;
          console.log('[DevicePanel] profile loaded', { hasToken: !!profileRef.current.accessToken });
        }
      } catch {
        console.warn('[DevicePanel] Profile fetch failed, panel auth will use defaults');
      }
      const phoneInfo = buildPhoneInfo();

      // 4. Create panel session with sync data (matching Vue: only language/appType/phoneInfo)
      const syncData = {
        language: 'zh-CN',
        appType: '0',
        phoneInfo,
      };

      const fsResponse = await fetch('/__panel_fs__/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ panelUrl, syncData }),
      });

      const fsData = await fsResponse.json();

      if (!fsData.success) {
        throw new Error(fsData.message || '面板会话创建失败');
      }

      const { entryUrl, sessionId, fileCount } = fsData.data;
      console.log('[DevicePanel] panel ready', { fileCount, entryUrl });

      panelSessionRef.current = {
        entryUrl,
        revoke: () => {
          fetch('/__panel_fs__/close', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessionId }),
          }).catch(() => {});
        },
        fileCount,
        sessionId,
      };

      setIframeSrc(entryUrl);
    } catch (err) {
      console.error('[DevicePanel] load failed', err);
      setError((err as Error).message || '面板加载失败');
    } finally {
      setLoading(false);
    }
  }, [deviceId, currentHomeId, handleBack]);

  useEffect(() => {
    if (deviceId) {
      loadPanel();
    }
  }, [deviceId, loadPanel]);

  return (
    <div className="device-panel-page">
      <header className="panel-toolbar">
        <button
          type="button"
          onClick={handleBack}
          className="back-btn flex items-center gap-2 px-4 py-2 text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          返回
        </button>
        <div className="toolbar-title" title={deviceName}>
          {deviceName || '设备面板'}
        </div>
        <div className="toolbar-extra">
          {error && (
            <button
              type="button"
              onClick={loadPanel}
              className="flex items-center gap-2 px-4 py-2 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              重试
            </button>
          )}
        </div>
      </header>

      <div className="panel-body">
        {loading && (
          <div className="panel-state">
            <div className="flex flex-col items-center gap-4">
              <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-gray-500 dark:text-gray-400">正在加载设备面板...</p>
            </div>
          </div>
        )}

        {!loading && error && (
          <div className="panel-state panel-error">
            <div className="text-center">
              <div className="w-16 h-16 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-3xl">!</span>
              </div>
              <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">{error}</h3>
              <p className="text-gray-500 dark:text-gray-400 mb-6">请检查该产品是否已配置面板，或稍后重试</p>
              <div className="flex gap-3 justify-center">
                <button
                  type="button"
                  onClick={loadPanel}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  重试
                </button>
                <button
                  type="button"
                  onClick={handleBack}
                  className="px-6 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  返回列表
                </button>
              </div>
            </div>
          </div>
        )}

        {!loading && !error && iframeSrc && (
          <iframe
            ref={iframeRef}
            className="panel-iframe"
            title="device-panel"
            src={iframeSrc}
            allow="clipboard-read; clipboard-write"
          />
        )}
      </div>

      <style>{`
        .device-panel-page {
          display: flex;
          flex-direction: column;
          height: calc(100vh - 64px);
          margin: -16px;
          background: var(--bg-elevated, #fff);
        }

        .panel-toolbar {
          display: flex;
          align-items: center;
          gap: 8px;
          height: 48px;
          padding: 0 12px;
          border-bottom: 1px solid var(--border-color, #f0f0f0);
          background: var(--bg-elevated, #fff);
          flex-shrink: 0;
        }

        .back-btn {
          color: var(--text-heading, #1f1f1f);
          padding-inline: 4px;
        }

        .toolbar-title {
          flex: 1;
          min-width: 0;
          font-size: 16px;
          font-weight: 600;
          color: var(--text-heading, #1f1f1f);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .toolbar-extra {
          display: flex;
          align-items: center;
          gap: 4px;
          flex-shrink: 0;
        }

        .panel-body {
          position: relative;
          flex: 1;
          min-height: 0;
          overflow: hidden;
        }

        .panel-iframe {
          display: block;
          width: 100%;
          height: 100%;
          border: 0;
          background: #fff;
        }

        .panel-state {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          padding: 24px;
        }

        .panel-error {
          align-items: flex-start;
          padding-top: 48px;
        }
      `}</style>
    </div>
  );
}