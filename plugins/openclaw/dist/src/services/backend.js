import axios from "axios";
import { logger } from "../utils/logger.js";
export class HeimanBackendClient {
    constructor(config) {
        this.baseUrl = config.backend_url || "http://localhost:1912";
    }
    async listSensors() {
        try {
            const response = await axios.get(`${this.baseUrl}/api/sensors`);
            return response.data;
        }
        catch (error) {
            logger.error("Failed to list sensors:", error);
            return [];
        }
    }
    async getSensor(did) {
        try {
            const response = await axios.get(`${this.baseUrl}/api/sensors/${did}`);
            return response.data;
        }
        catch (error) {
            logger.error(`Failed to get sensor ${did}:`, error);
            return null;
        }
    }
    async listEvents() {
        try {
            const response = await axios.get(`${this.baseUrl}/api/events`);
            return response.data;
        }
        catch (error) {
            logger.error("Failed to list events:", error);
            return [];
        }
    }
    async acknowledgeEvent(eventId) {
        try {
            await axios.post(`${this.baseUrl}/api/events/${eventId}/acknowledge`);
            return true;
        }
        catch (error) {
            logger.error(`Failed to acknowledge event ${eventId}:`, error);
            return false;
        }
    }
    async listRules() {
        try {
            const response = await axios.get(`${this.baseUrl}/api/rules`);
            return response.data;
        }
        catch (error) {
            logger.error("Failed to list rules:", error);
            return [];
        }
    }
    async toggleRule(ruleId, enabled) {
        try {
            await axios.put(`${this.baseUrl}/api/rules/${ruleId}/toggle`, { enabled });
            return true;
        }
        catch (error) {
            logger.error(`Failed to toggle rule ${ruleId}:`, error);
            return false;
        }
    }
}
