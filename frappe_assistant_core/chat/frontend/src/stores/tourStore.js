import { defineStore } from "pinia";
import { ref } from "vue";

// Bump this when a new scene is added to FeatureReel or the script changes
// meaningfully. Existing users will see the reel once on their next page
// load after the bump; they can dismiss with Skip or watch through.
//
// Format: "MAJOR.MINOR" — MAJOR for new features/scenes, MINOR for copy/visual
// tweaks. Users with a stamped version >= LAST_TOUR_VERSION never auto-replay.
export const LAST_TOUR_VERSION = "2.0";

const STORAGE_KEY = "faco.lastSeenTourVersion";

function readSeenVersion() {
	try {
		return window.localStorage.getItem(STORAGE_KEY) || "";
	} catch {
		// localStorage can throw in private mode / SSR. Treat as never-seen and move on.
		return "";
	}
}

function writeSeenVersion(v) {
	try {
		window.localStorage.setItem(STORAGE_KEY, v);
	} catch {
		// Best-effort. If write fails (storage disabled), the user will see the
		// reel again next load — annoying, not broken.
	}
}

// Drives the global FeatureReel modal. Anywhere in the app, call
// `useTourStore().open()` to play the reel; the TourPlayer component
// (mounted in App.vue) listens to `isOpen` and renders the reel as an overlay.
export const useTourStore = defineStore("tour", () => {
	const isOpen = ref(false);

	function open() {
		isOpen.value = true;
	}

	// Marks the current version as seen and closes the reel. Called when
	// FeatureReel emits 'complete' (Skip, Continue past the last scene, or
	// keyboard Escape).
	function close() {
		isOpen.value = false;
		writeSeenVersion(LAST_TOUR_VERSION);
	}

	// Call once on app boot after auth. Auto-opens the reel for users whose
	// stamped version is behind LAST_TOUR_VERSION. First-time users (no stamp)
	// don't get the auto-play — the new-user onboarding wizard already shows
	// the reel inline. This branch is purely for *returning* users who
	// haven't seen the latest features.
	function init() {
		const seen = readSeenVersion();
		if (!seen) {
			// New user — onboarding wizard handles it. Stamp so we don't auto-replay later.
			writeSeenVersion(LAST_TOUR_VERSION);
			return;
		}
		if (seen !== LAST_TOUR_VERSION) {
			open();
		}
	}

	return { isOpen, open, close, init };
});
