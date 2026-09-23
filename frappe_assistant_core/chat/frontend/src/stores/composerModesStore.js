import { ref } from "vue";
import { defineStore } from "pinia";
import { logger } from "@/utils/logger";

const STORAGE_KEY = "faco_composer_modes";
const MAX_SESSIONS = 50;
// Modes can be flipped before the first send, when no session id exists yet.
const PENDING = "__pending__";

function emptyModes() {
	return { webSearch: false, thinking: false };
}

export const useComposerModesStore = defineStore("composerModes", () => {
	const bySession = ref(load());

	function load() {
		try {
			return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
		} catch (e) {
			logger.warn("Failed to load composer modes:", e);
			return {};
		}
	}

	function persist() {
		const keys = Object.keys(bySession.value);
		if (keys.length > MAX_SESSIONS) {
			for (const key of keys.slice(0, keys.length - MAX_SESSIONS)) {
				delete bySession.value[key];
			}
		}
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(bySession.value));
		} catch (e) {
			logger.warn("Failed to save composer modes:", e);
		}
	}

	function modesFor(sessionId) {
		return { ...emptyModes(), ...(bySession.value[sessionId || PENDING] || {}) };
	}

	function toggle(sessionId, mode) {
		const key = sessionId || PENDING;
		const next = { ...modesFor(key), [mode]: !modesFor(key)[mode] };
		delete bySession.value[key];
		bySession.value[key] = next;
		persist();
	}

	function adoptPendingSession(sessionId) {
		const pending = bySession.value[PENDING];
		if (!pending || !sessionId) return;
		delete bySession.value[PENDING];
		bySession.value[sessionId] = pending;
		persist();
	}

	return { bySession, modesFor, toggle, adoptPendingSession };
});
