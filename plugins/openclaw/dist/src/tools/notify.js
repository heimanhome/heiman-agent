import { logger } from "../utils/logger.js";
import { getPluginConfig } from "../config.js";
export function registerNotifyTool(api) {
    const notifyFactory = (_ctx) => ({
        name: "heiman_notify",
        label: "Heiman Notification",
        description: "Send notification to Heiman Agent users",
        parameters: {
            type: "object",
            properties: {
                message: {
                    type: "string",
                    description: "Notification message",
                },
                level: {
                    type: "string",
                    enum: ["info", "warn", "error"],
                    description: "Notification level",
                },
            },
            required: ["message"],
        },
        async execute(_toolCallId, params) {
            const { message, level } = params;
            const config = getPluginConfig(api);
            const sessionKey = config.notifySessionKey || "main";
            try {
                await api.runtime.im.sendText({
                    sessionKey,
                    text: `[Heiman] ${level?.toUpperCase() || "INFO"}: ${message}`,
                });
                logger.info(`Notification sent: ${message}`);
                return { success: true };
            }
            catch (error) {
                logger.error("Failed to send notification:", error);
                return { success: false, error: String(error) };
            }
        },
    });
    api.registerTool?.(notifyFactory, { name: "heiman_notify" });
}
