export const createMockApi = () => ({
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
            mutateConfigFile: async () => { },
        },
        im: {
            sendText: async (params) => console.log("[mock-sdk] Send text:", params),
        },
        subagent: {
            run: async (params) => ({ runId: `mock-run-${Date.now()}` }),
            waitForRun: async () => ({ status: "ok" }),
        },
    },
    config: {},
});
