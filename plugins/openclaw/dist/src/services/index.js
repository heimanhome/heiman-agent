import { logger } from "../utils/logger.js";
import { getPluginConfig } from "../config.js";
import { HeimanBackendClient } from "./backend.js";
let backendClient;
export function getBackendClient(api) {
    if (!backendClient) {
        const config = getPluginConfig(api);
        backendClient = new HeimanBackendClient(config);
    }
    return backendClient;
}
export function registerServices(api) {
    logger.info("Registering Heiman services");
    const config = getPluginConfig(api);
    const service = {
        name: "heiman-backend",
        description: "Heiman Agent Backend Service",
        start: async () => {
            logger.info("Heiman backend service started");
        },
        stop: async () => {
            logger.info("Heiman backend service stopped");
        },
    };
    api.registerService?.(service);
}
