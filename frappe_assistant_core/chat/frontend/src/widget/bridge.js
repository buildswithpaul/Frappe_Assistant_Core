import { logger } from "@/utils/logger";

/** Launcher ⇄ panel channel. Plain JS so the launcher never loads Vue. */
const listeners = new Map();

export const bridge = {
	state: { sessionId: null, restored: false, open: false, access: null, attention: false, micRequested: false },
	on(event, fn) {
		if (!listeners.has(event)) listeners.set(event, new Set());
		listeners.get(event).add(fn);
		return () => listeners.get(event).delete(fn);
	},
	emit(event, payload) {
		for (const fn of listeners.get(event) || []) {
			try {
				fn(payload);
			} catch (err) {
				logger.error("[FAC widget]", event, err);
			}
		}
	},
};
