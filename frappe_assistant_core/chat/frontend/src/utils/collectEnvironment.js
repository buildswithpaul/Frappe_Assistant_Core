/**
 * Collect non-sensitive app/environment info to attach to a support report.
 * Shown to the user before send (never silent).
 *
 * Versions come from the server (support.getEnvironment) — the SPA shell has
 * no version meta tags to read, so anything derived client-side could only
 * ever be "unknown". The browser contributes the half only it knows.
 */
import { api } from "@/api/client";

let pending = null;

/**
 * Fetch the server half once per page load. Versions can't change without a
 * restart, so the in-flight promise is the cache. Never rejects — a support
 * report is worth sending even when we can't describe the instance.
 */
export function loadServerEnvironment() {
	if (!pending) {
		pending = api.support.getEnvironment().catch(() => ({}));
	}
	return pending;
}

export function collectEnvironment(server = {}, extra = {}) {
	return {
		...server,
		browser: navigator.userAgent || "unknown",
		platform: navigator.platform || "unknown",
		language: navigator.language || "unknown",
		...extra, // e.g. { model: activeModelId }
	};
}
