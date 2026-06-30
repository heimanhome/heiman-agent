let api;
export const logger = {
    init(api_) {
        api = api_;
    },
    debug(...args) {
        if (!api)
            return;
        api.logger.debug(`[heiman]`, ...args);
    },
    info(...args) {
        if (!api)
            return;
        api.logger.info(`[heiman]`, ...args);
    },
    warn(...args) {
        if (!api)
            return;
        api.logger.warn(`[heiman]`, ...args);
    },
    error(...args) {
        if (!api)
            return;
        api.logger.error(`[heiman]`, ...args);
    },
};
