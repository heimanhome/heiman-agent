import type { OpenClawPluginApi } from "@openclaw/plugin-sdk";

let api: OpenClawPluginApi | undefined;

export const logger = {
  init(api_: OpenClawPluginApi) {
    api = api_;
  },
  debug(...args: unknown[]) {
    if (!api) return;
    api.logger.debug(`[heiman]`, ...args);
  },
  info(...args: unknown[]) {
    if (!api) return;
    api.logger.info(`[heiman]`, ...args);
  },
  warn(...args: unknown[]) {
    if (!api) return;
    api.logger.warn(`[heiman]`, ...args);
  },
  error(...args: unknown[]) {
    if (!api) return;
    api.logger.error(`[heiman]`, ...args);
  },
};
