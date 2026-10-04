import { ref } from "vue";
import { defineStore } from "pinia";
import { logger } from "@/utils/logger";

const STORAGE_KEY = "faco_composer_modes";
const MAX_SESSIONS = 50;
// Modes can be flipped before the first send, when no session id exists yet.
const PENDING = "__pending__";

export const EFFORT_LEVELS = ["off", "low", "medium", "high", "xhigh", "max"];

function emptyModes() {
	return { webSearch: false, effort: "off" };
}

// Conversations saved before the level selector stored a boolean `thinking`.
// "On" meant high effort, so that is what it becomes.
function normalise(saved) {
	const { thinking, ...rest } = saved || {};
	const modes = { ...emptyModes(), ...rest };
	if (!EFFORT_LEVELS.includes(rest.effort)) {
		modes.effort = thinking === true ? "high" : "off";
	}
	return modes;
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
		return normalise(bySession.value[sessionId || PENDING]);
	}

	function save(sessionId, next) {
		const key = sessionId || PENDING;
		delete bySession.value[key];
		bySession.value[key] = next;
		persist();
	}

	function toggle(sessionId, mode) {
		const current = modesFor(sessionId);
		if (mode === "thinking") {
			// The legacy on/off control, shown when AR publishes no levels.
			save(sessionId, { ...current, effort: current.effort === "off" ? "high" : "off" });
			return;
		}
		save(sessionId, { ...current, [mode]: !current[mode] });
	}

	function setEffort(sessionId, level) {
		if (!EFFORT_LEVELS.includes(level)) return;
		save(sessionId, { ...modesFor(sessionId), effort: level });
	}

	function adoptPendingSession(sessionId) {
		const pending = bySession.value[PENDING];
		if (!pending || !sessionId) return;
		delete bySession.value[PENDING];
		bySession.value[sessionId] = pending;
		persist();
	}

	return { bySession, modesFor, toggle, setEffort, adoptPendingSession };
});
