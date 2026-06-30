import { kAgentWebhook } from "./agent.js";
const webhooks = [kAgentWebhook];
export function registerHttpRoutes(api) {
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
