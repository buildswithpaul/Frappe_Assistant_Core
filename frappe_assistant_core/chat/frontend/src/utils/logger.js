/**
 * FACO Logger — Environment-aware logging utility.
 *
 * In development: all levels log to console.
 * In production: only error/warn log; debug/info/log are silenced.
 *
 * Usage:
 *   import { logger } from '@/utils/logger'
 *   logger.error('Payment failed:', err)    // always logs
 *   logger.warn('Token expiring soon')      // always logs
 *   logger.info('Socket connected')         // dev only
 *   logger.debug('Stream chunk:', data)     // dev only
 */

const isDev = import.meta.env.DEV;

const noop = () => {};

export const logger = {
	error: (...args) => console.error("[FACO]", ...args), // eslint-disable-line no-console
	warn: (...args) => console.warn("[FACO]", ...args), // eslint-disable-line no-console
	info: isDev ? (...args) => console.info("[FACO]", ...args) : noop, // eslint-disable-line no-console
	debug: isDev ? (...args) => console.log("[FACO]", ...args) : noop, // eslint-disable-line no-console
	log: isDev ? (...args) => console.log("[FACO]", ...args) : noop, // eslint-disable-line no-console
};
