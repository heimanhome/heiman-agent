export type OpenClawPluginApi = {
  id: string;
  name: string;
  description: string;
  configSchema?: unknown;
  logger: {
    debug: (...args: unknown[]) => void;
    info: (...args: unknown[]) => void;
    warn: (...args: unknown[]) => void;
    error: (...args: unknown[]) => void;
  };
  tools: {
    register: (tool: {
      name: string;
      description: string;
      parameters: unknown;
      execute: (params: unknown) => Promise<unknown>;
    }) => void;
  };
  http: {
    register: (route: {
      path: string;
      method: string;
      handler: (req: { body: unknown }) => Promise<unknown>;
    }) => void;
  };
  on: (
    event: string,
    handler: (
      event?: { prompt?: string },
      ctx?: { sessionKey?: string; trigger?: string }
    ) => Promise<unknown>
  ) => void;
  hooks: {
    on: (event: string, handler: (ctx: unknown) => Promise<void>) => void;
  };
  registerTool?: (
    factory: (ctx: unknown) => {
      name: string;
      label: string;
      description: string;
      parameters: unknown;
      execute: (toolCallId: unknown, params: unknown) => Promise<unknown>;
    },
    options?: { name: string }
  ) => void;
  registerService?: (service: {
    name: string;
    description: string;
    start: () => Promise<void>;
    stop: () => Promise<void>;
  }) => void;
  runtime: {
    config: {
      current?: () => OpenClawConfig;
      mutateConfigFile: (options: {
        afterWrite: { mode: string; reason: string };
        mutate: (draft: unknown) => void;
      }) => Promise<void>;
    };
    im: {
      sendText: (params: { sessionKey: string; text: string }) => Promise<void>;
    };
    subagent: {
      run: (params: {
        sessionKey: string;
        message: string;
        lane?: string;
        deliver: boolean;
        idempotencyKey: string;
        extraSystemPrompt?: string;
      }) => Promise<{ runId: string }>;
      waitForRun: (params: { runId: string; timeoutMs?: number }) => Promise<{
        status: "ok" | "error" | "timeout";
        error?: string;
      }>;
      deleteSession?: (params: { sessionKey: string; deleteTranscript?: boolean }) => Promise<void>;
    };
  };
  config: OpenClawConfig;
};

export type OpenClawConfig = {
  plugins?: {
    entries?: Record<string, { config?: unknown }>;
  };
};

export type OpenClawPluginConfigSchema = {
  jsonSchema: unknown;
  uiHints: unknown;
};

export const createMockApi = (): OpenClawPluginApi => ({
  id: "mock-api",
  name: "Mock API",
  description: "Mock OpenClaw Plugin API",
  logger: {
    debug: (...args) => console.debug("[mock-sdk]", ...args),
    info: (...args) => console.info("[mock-sdk]", ...args),
    warn: (...args) => console.warn("[mock-sdk]", ...args),
    error: (...args) => console.error("[mock-sdk]", ...args),
  },
  tools: {
    register: (tool) => console.log("[mock-sdk] Registered tool:", tool.name),
  },
  http: {
    register: (route) => console.log("[mock-sdk] Registered route:", route.path),
  },
  on: (event) => console.log("[mock-sdk] Registered event listener:", event),
  hooks: {
    on: (event) => console.log("[mock-sdk] Registered hook:", event),
  },
  registerTool: (factory, options) => console.log("[mock-sdk] Registered tool via factory:", options?.name),
  registerService: (service) => console.log("[mock-sdk] Registered service:", service.name),
  runtime: {
    config: {
      current: () => ({}),
      mutateConfigFile: async () => {},
    },
    im: {
      sendText: async (params) => console.log("[mock-sdk] Send text:", params),
    },
    subagent: {
      run: async (params) => ({ runId: `mock-run-${Date.now()}` }),
      waitForRun: async () => ({ status: "ok" as const }),
    },
  },
  config: {},
});
