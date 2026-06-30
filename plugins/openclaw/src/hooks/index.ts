import type { OpenClawPluginApi } from "@openclaw/plugin-sdk";
import { logger } from "../utils/logger.js";

export function registerHooks(api: OpenClawPluginApi) {
  logger.info("Registering Heiman hooks");

  api.on("before_prompt_build", async (event?: { prompt?: string }, ctx?: { sessionKey?: string; trigger?: string }) => {
    logger.debug("before_prompt_build hook triggered");
    return {};
  });

  api.on("after_message", async (event?: { prompt?: string }, ctx?: { sessionKey?: string; trigger?: string }) => {
    logger.debug("after_message hook triggered");
    return {};
  });
}
