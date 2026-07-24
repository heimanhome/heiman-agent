import { authManager, type UserProfile } from './auth-manager';
import type { SensorData } from '../types';
import {
  sensorApi,
  homeApi,
  deviceApi,
  authApi,
  type ApiResponse,
  type HomeData,
  type DeviceData,
} from './client';

export interface ApiRequestInfo {
  url: string;
  method: string;
  status: 'pending' | 'resolved' | 'rejected';
  statusCode: number | null;
  responseTime: number;
  timestamp: string;
  error?: string;
  responseData?: unknown;
}

export interface MqttConnectionInfo {
  broker: string;
  port: number;
  sslEnabled: boolean;
  clientId: string;
  status: 'disconnected' | 'connecting' | 'connected';
  lastConnectedAt?: string;
  lastDisconnectedAt?: string;
  reconnectAttempts: number;
  messages: MqttMessage[];
}

export interface MqttMessage {
  timestamp: string;
  topic: string;
  payload: string;
  direction: 'in' | 'out';
}

export interface StatusCheckResult {
  timestamp: string;
  auth: AuthCheckResult;
  api: ApiCheckResult;
  mqtt: MqttCheckResult;
  overall: 'healthy' | 'degraded' | 'critical';
}

export interface AuthCheckResult {
  isAuthenticated: boolean;
  profile: UserProfile | null;
  userId: string | null;
}

export interface ApiCheckResult {
  userInfo: ApiRequestInfo | null;
  homeInfo: ApiRequestInfo | null;
  deviceInfo: ApiRequestInfo | null;
  sensorInfo: ApiRequestInfo | null;
  allSuccess: boolean;
}

export interface MqttCheckResult {
  mcpConfig: MqttConfigInfo | null;
  mqttConfig: MqttConfigInfo | null;
  connectionStatus: 'unknown' | 'connected' | 'disconnected';
}

export interface MqttConfigInfo {
  broker: string;
  port: number;
  sslEnabled: boolean;
  keepalive: number;
  protocol: string;
}

export class StatusChecker {
  private static instance: StatusChecker;
  private apiRequests: Map<string, ApiRequestInfo> = new Map();
  private mqttMessages: MqttMessage[] = [];
  private MAX_MESSAGES = 10;

  private constructor() {}

  public static getInstance(): StatusChecker {
    if (!StatusChecker.instance) {
      StatusChecker.instance = new StatusChecker();
    }
    return StatusChecker.instance;
  }

  public async runFullCheck(): Promise<StatusCheckResult> {
    const timestamp = new Date().toISOString();
    
    console.log('[StatusChecker] Starting full status check...');
    
    const [authCheck, apiCheck, mqttCheck] = await Promise.all([
      this.checkAuth(),
      this.checkAllApis(),
      this.checkMqttConfig(),
    ]);

    let overall: 'healthy' | 'degraded' | 'critical' = 'healthy';
    
    if (!authCheck.isAuthenticated) {
      overall = 'critical';
    } else if (!apiCheck.allSuccess) {
      overall = 'degraded';
    }

    const result: StatusCheckResult = {
      timestamp,
      auth: authCheck,
      api: apiCheck,
      mqtt: mqttCheck,
      overall,
    };

    console.log('[StatusChecker] Full status check completed:', JSON.stringify(result, null, 2));
    
    return result;
  }

  public async checkAuth(): Promise<AuthCheckResult> {
    const profile = authManager.getProfile();
    
    const result: AuthCheckResult = {
      isAuthenticated: authManager.isAuthenticated(),
      profile,
      userId: profile?.userId || null,
    };

    console.log('[StatusChecker] Auth check:', result);
    return result;
  }

  public async checkAllApis(): Promise<ApiCheckResult> {
    const [userInfo, homeInfo, deviceInfo, sensorInfo] = await Promise.allSettled([
      this.checkApi('userInfo', () => authApi.getProfile()),
      this.checkApi('homeInfo', () => homeApi.getAll()),
      this.checkApi('deviceInfo', () => deviceApi.getAll()),
      this.checkApi('sensorInfo', () => sensorApi.getAll()),
    ]);

    const results = {
      userInfo: userInfo.status === 'fulfilled' ? userInfo.value : null,
      homeInfo: homeInfo.status === 'fulfilled' ? homeInfo.value : null,
      deviceInfo: deviceInfo.status === 'fulfilled' ? deviceInfo.value : null,
      sensorInfo: sensorInfo.status === 'fulfilled' ? sensorInfo.value : null,
      allSuccess: [userInfo, homeInfo, deviceInfo, sensorInfo].every(r => r.status === 'fulfilled'),
    };

    console.log('[StatusChecker] API check:', results);
    return results;
  }

  private async checkApi(name: string, fn: () => Promise<{ data: ApiResponse }>): Promise<ApiRequestInfo> {
    const startTime = Date.now();
    const timestamp = new Date().toISOString();
    
    let requestInfo: ApiRequestInfo = {
      url: name,
      method: 'GET',
      status: 'pending',
      statusCode: null,
      responseTime: 0,
      timestamp,
    };

    try {
      const response = await fn();
      const responseTime = Date.now() - startTime;
      
      requestInfo = {
        ...requestInfo,
        status: 'resolved',
        statusCode: 200,
        responseTime,
        responseData: response.data,
      };

      this.validateResponseData(name, response.data);
    } catch (error) {
      const responseTime = Date.now() - startTime;
      
      requestInfo = {
        ...requestInfo,
        status: 'rejected',
        statusCode: error instanceof Error ? 0 : (error as { status?: number }).status || 0,
        responseTime,
        error: error instanceof Error ? error.message : String(error),
      };
    }

    this.apiRequests.set(name, requestInfo);
    return requestInfo;
  }

  private validateResponseData(name: string, response: ApiResponse): void {
    const expectedFields: Record<string, string[]> = {
      userInfo: ['username', 'email', 'bindStatus'],
      homeInfo: ['id', 'name', 'devices'],
      deviceInfo: ['id', 'name', 'type', 'status'],
      sensorInfo: ['did', 'type', 'value'],
    };

    const fields = expectedFields[name];
    if (!fields || !response.data) return;

    const data = response.data;
    const dataArray = Array.isArray(data) ? data : [data];

    if (dataArray.length > 0) {
      const firstItem = dataArray[0];
      const missingFields = fields.filter(field => !(field in firstItem));
      
      if (missingFields.length > 0) {
        console.warn(`[StatusChecker] ${name} response missing fields: ${missingFields.join(', ')}`);
      }
    }
  }

  public async checkMqttConfig(): Promise<MqttCheckResult> {
    const mcpConfig = this.loadMcpConfig();
    const mqttConfig = this.loadMqttConfig();

    console.log('[StatusChecker] MQTT config check:', { mcpConfig, mqttConfig });

    return {
      mcpConfig,
      mqttConfig,
      connectionStatus: 'unknown',
    };
  }

  private loadMcpConfig(): MqttConfigInfo | null {
    try {
      return {
        broker: 'spmqtt.heiman.cn',
        port: 1884,
        sslEnabled: true,
        keepalive: 60,
        protocol: 'MQTTv311',
      };
    } catch {
      return null;
    }
  }

  private loadMqttConfig(): MqttConfigInfo | null {
    try {
      return {
        broker: 'spmqtt.heiman.cn',
        port: 1884,
        sslEnabled: true,
        keepalive: 60,
        protocol: 'MQTTv311',
      };
    } catch {
      return null;
    }
  }

  public addMqttMessage(topic: string, payload: string, direction: 'in' | 'out'): void {
    const message: MqttMessage = {
      timestamp: new Date().toISOString(),
      topic,
      payload: payload.length > 200 ? payload.substring(0, 200) + '...' : payload,
      direction,
    };

    this.mqttMessages.unshift(message);
    
    if (this.mqttMessages.length > this.MAX_MESSAGES) {
      this.mqttMessages.pop();
    }
  }

  public getApiRequests(): Map<string, ApiRequestInfo> {
    return this.apiRequests;
  }

  public getMqttMessages(): MqttMessage[] {
    return this.mqttMessages;
  }

  public generateReport(): string {
    const report: Record<string, unknown> = {
      timestamp: new Date().toISOString(),
      auth: {
        isAuthenticated: authManager.isAuthenticated(),
      },
      apiRequests: Array.from(this.apiRequests.entries()).map(([key, value]) => ({
        name: key,
        ...value,
      })),
      mqttMessages: this.mqttMessages,
      localStorageKeys: Object.keys(localStorage).filter(k => k.startsWith('heiman_')),
    };

    return JSON.stringify(report, null, 2);
  }
}

export const statusChecker = StatusChecker.getInstance();