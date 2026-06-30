import type { OpenClawPluginApi } from "@openclaw/plugin-sdk";
import {
  kPluginDescription,
  kPluginId,
  kPluginName,
  HeimanPluginConfigSchema,
} from "./config.js";
import { registerServices } from "./services/index.js";
import { registerHooks } from "./hooks/index.js";
import { registerHttpRoutes } from "./webhooks/index.js";
import { registerNotifyTool } from "./tools/notify.js";
import { logger } from "./utils/logger.js";

export default {
  id: kPluginId,
  name: kPluginName,
  description: kPluginDescription,
  configSchema: HeimanPluginConfigSchema,
  register(api: OpenClawPluginApi) {
    logger.init(api);
    logger.info("Initializing Heiman Agent OpenClaw Plugin");

    try {
      registerServices(api);
      logger.info("Services registered");
    } catch (e) {
      logger.error("Failed to register services:", e);
    }

    try {
      registerHooks(api);
      logger.info("Hooks registered");
    } catch (e) {
      logger.error("Failed to register hooks:", e);
    }

    try {
      registerHttpRoutes(api);
      logger.info("HTTP routes registered");
    } catch (e) {
      logger.error("Failed to register HTTP routes:", e);
    }

    try {
      registerNotifyTool(api);
      logger.info("Notification tool registered");
    } catch (e) {
      logger.error("Failed to register notify tool:", e);
    }

    logger.info("Heiman Agent OpenClaw Plugin initialized successfully");
  },
};
