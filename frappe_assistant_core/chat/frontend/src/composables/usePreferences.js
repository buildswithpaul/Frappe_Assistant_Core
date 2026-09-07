import { reactive } from "vue";

const STORAGE_KEY = "faco-preferences";

const preferences = reactive({
	showTimestamps: false,
	reduceMotion: false,
	highContrast: false,
	largeText: false,
	chatWidth: "wide",
});

let initialized = false;

function load() {
	if (initialized) return;
	initialized = true;

	const saved = localStorage.getItem(STORAGE_KEY);
	if (saved) {
		try {
			const parsed = JSON.parse(saved);
			// Only assign known keys to avoid leftover stubs
			for (const key of Object.keys(preferences)) {
				if (key in parsed) preferences[key] = parsed[key];
			}
		} catch {
			// Ignore corrupt localStorage
		}
	}
	applyAccessibility();
}

function save() {
	localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...preferences }));
	applyAccessibility();
}

function applyAccessibility() {
	const root = document.documentElement;
	root.classList.toggle("reduce-motion", preferences.reduceMotion);
	root.classList.toggle("high-contrast", preferences.highContrast);
	root.classList.toggle("large-text", preferences.largeText);
}

export function usePreferences() {
	load();
	return { preferences, savePreferences: save };
}
