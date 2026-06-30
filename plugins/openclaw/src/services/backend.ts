import axios from "axios";
import { logger } from "../utils/logger.js";
import type { HeimanPluginConfig } from "../config.js";

export interface Sensor {
  did: string;
  name: string;
  type: string;
  status: string;
  value: number;
  unit: string;
  last_update: string;
}

export interface Event {
  event_id: string;
  sensor_did: string;
  level: string;
  message: string;
  acknowledged: boolean;
  timestamp: string;
}

export interface Rule {
  rule_id: string;
  name: string;
  condition: string;
  action: string;
  enabled: boolean;
  created_at: string;
}

export class HeimanBackendClient {
  private baseUrl: string;

  constructor(config: HeimanPluginConfig) {
    this.baseUrl = config.backend_url || "http://localhost:1912";
  }

  async listSensors(): Promise<Sensor[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/sensors`);
      return response.data;
    } catch (error) {
      logger.error("Failed to list sensors:", error);
      return [];
    }
  }

  async getSensor(did: string): Promise<Sensor | null> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/sensors/${did}`);
      return response.data;
    } catch (error) {
      logger.error(`Failed to get sensor ${did}:`, error);
      return null;
    }
  }

  async listEvents(): Promise<Event[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/events`);
      return response.data;
    } catch (error) {
      logger.error("Failed to list events:", error);
      return [];
    }
  }

  async acknowledgeEvent(eventId: string): Promise<boolean> {
    try {
      await axios.post(`${this.baseUrl}/api/events/${eventId}/acknowledge`);
      return true;
    } catch (error) {
      logger.error(`Failed to acknowledge event ${eventId}:`, error);
      return false;
    }
  }

  async listRules(): Promise<Rule[]> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/rules`);
      return response.data;
    } catch (error) {
      logger.error("Failed to list rules:", error);
      return [];
    }
  }

  async toggleRule(ruleId: string, enabled: boolean): Promise<boolean> {
    try {
      await axios.put(`${this.baseUrl}/api/rules/${ruleId}/toggle`, { enabled });
      return true;
    } catch (error) {
      logger.error(`Failed to toggle rule ${ruleId}:`, error);
      return false;
    }
  }
}
