import type { OpenClawPluginApi } from "@openclaw/plugin-sdk";
import { kAgentWebhook } from "./agent.js";

export interface WebhookEntry<T = unknown> {
  name: string;
  action: (ctx: { api: OpenClawPluginApi; payload: T }) => Promise<unknown>;
}

const webhooks: WebhookEntry<unknown>[] = [kAgentWebhook as WebhookEntry<unknown>];

export function registerHttpRoutes(api: OpenClawPluginApi) {
  webhooks.forEach((webhook) => {
    api.http?.register({
      path: `/heiman/${webhook.name}`,
      method: "POST",
      handler: async (req) => {
        return webhook.action({ api, payload: req.body });
      },
    });
  });
}
