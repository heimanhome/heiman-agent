import { logger } from "../utils/logger.js";
import type { WebhookEntry } from "./index.js";

interface IRequestBody {
  message: string;
  sessionKey?: string;
  lane?: string;
  idempotencyKey?: string;
  extraSystemPrompt?: string;
  traceId?: string;
  timeoutMs?: number;
}

const DEFAULT_WAIT_MS = 180_000;

export const kAgentWebhook: WebhookEntry<IRequestBody> = {
  name: "agent",
  action: async ({ api, payload }) => {
    const {
      message,
      extraSystemPrompt,
      sessionKey = "main",
      lane,
      idempotencyKey = crypto.randomUUID(),
      traceId,
      timeoutMs,
    } = payload;

    const result = await api.runtime.subagent.run({
      sessionKey,
      message,
      lane,
      deliver: false,
      idempotencyKey,
      extraSystemPrompt,
    });

    if (traceId) {
      logger.info(`Trace link registered: ${result.runId} -> ${traceId}`);
    }

    const wait = (await api.runtime.subagent.waitForRun({
      runId: result.runId,
      timeoutMs: timeoutMs ?? DEFAULT_WAIT_MS,
    })) as { status: "ok" | "error" | "timeout"; error?: string };

    return {
      runId: result.runId,
      status: wait.status,
      error: wait.error,
    };
  },
};
