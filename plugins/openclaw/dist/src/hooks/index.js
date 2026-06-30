import { logger } from "../utils/logger.js";
export function registerHooks(api) {
    logger.info("Registering Heiman hooks");
    api.on("before_prompt_build", async (event, ctx) => {
        logger.debug("before_prompt_build hook triggered");
        return {};
    });
    api.on("after_message", async (event, ctx) => {
        logger.debug("after_message hook triggered");
        return {};
    });
}
