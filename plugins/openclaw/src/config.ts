import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type {
  OpenClawConfig,
  OpenClawPluginApi,
  OpenClawPluginConfigSchema,
} from "@openclaw/plugin-sdk";
import pluginJson from "../openclaw.plugin.json" with { type: "json" };

export const kPluginRootDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
);

export const kPluginJSON = pluginJson;
export const kPluginId = pluginJson.id;
export const kPluginName = pluginJson.name;
export const kPluginDescription = pluginJson.description;

export interface HeimanPluginConfig {
  debug?: boolean;
  backend_url?: string;
  notifySessionKey?: string;
}

const HEIMAN_PLUGIN_CONFIG_SCHEMA = {
  jsonSchema: {
    title: "HeimanPluginConfig",
    type: "object",
    additionalProperties: true,
    properties: {
      debug: {
        type: "boolean",
        description: "调试模式",
      },
      backend_url: {
        type: "string",
        description: "Heiman Agent后端服务地址",
      },
      notifySessionKey: {
        type: "string",
        description: "通知目标sessionKey",
      },
    },
  },
  uiHints: {
    debug: {
      label: "调试模式",
      help: "打开调试模式，方便排查定位问题。",
    },
    backend_url: {
      label: "后端服务地址",
      help: "Heiman Agent后端API地址，默认http://localhost:1912",
    },
    notifySessionKey: {
      label: "通知目标Channel",
      help: "指定接收通知的IM channel session key。留空则自动选择最近活跃的channel。",
    },
  },
} as const satisfies OpenClawPluginConfigSchema;

export const HeimanPluginConfigSchema = HEIMAN_PLUGIN_CONFIG_SCHEMA;

const resolvePluginConfig = (config: unknown): HeimanPluginConfig => {
  const result: HeimanPluginConfig = {
    debug: false,
    backend_url: "http://localhost:1912",
    ...(config as HeimanPluginConfig),
  };
  return result;
};

let kPluginConfig: HeimanPluginConfig | undefined;

export function getRuntimeConfig(api: OpenClawPluginApi): OpenClawConfig {
  return (api.runtime.config?.current?.() ?? api.config) as OpenClawConfig;
}

export function getPluginConfig(api: OpenClawPluginApi): HeimanPluginConfig {
  if (kPluginConfig) return kPluginConfig;
  const cfg = getRuntimeConfig(api);
  const plugin = cfg.plugins?.entries?.[kPluginId];
  return resolvePluginConfig(plugin?.config);
}

export async function setPluginConfig(
  api: OpenClawPluginApi,
  config: Partial<HeimanPluginConfig>,
) {
  const cfg = getRuntimeConfig(api);
  const plugin = cfg.plugins?.entries?.[kPluginId];
  if (!plugin) {
    return;
  }
  const oldConfig = getPluginConfig(api);
  const newConfig = { ...oldConfig, ...config };
  kPluginConfig = newConfig;

  await api.runtime.config.mutateConfigFile({
    afterWrite: { mode: "none", reason: "plugin config update" },
    mutate(draft) {
      const draftConfig = draft as OpenClawConfig;
      if (!draftConfig.plugins?.entries?.[kPluginId]) return;
      draftConfig.plugins.entries[kPluginId] = {
        ...draftConfig.plugins.entries[kPluginId],
        config: newConfig,
      };
    },
  });
}
