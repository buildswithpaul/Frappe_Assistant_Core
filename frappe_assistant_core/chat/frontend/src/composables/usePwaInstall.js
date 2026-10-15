import { computed, ref } from "vue";

// Chrome and Edge fire `beforeinstallprompt` once, early, often before any
// component mounts. initPwaInstall() runs from main.js to catch it; the menu
// reads the result through usePwaInstall().
const deferredPrompt = ref(null);
const installed = ref(false);

function isStandalone() {
	return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

// iPhone and iPad offer no install prompt: the user adds the app from the Share
// menu. iPadOS reports itself as a Mac, so touch support tells the two apart.
function isIos() {
	const { userAgent, platform, maxTouchPoints } = window.navigator;
	return /iPhone|iPad|iPod/.test(userAgent) || (platform === "MacIntel" && maxTouchPoints > 1);
}

export function initPwaInstall() {
	installed.value = isStandalone();
	window.addEventListener("beforeinstallprompt", (event) => {
		event.preventDefault();
		deferredPrompt.value = event;
	});
	window.addEventListener("appinstalled", () => {
		installed.value = true;
		deferredPrompt.value = null;
	});
}

export function usePwaInstall() {
	const needsInstructions = computed(() => !deferredPrompt.value && isIos());
	const canInstall = computed(() => !installed.value && (Boolean(deferredPrompt.value) || needsInstructions.value));

	/** Shows the browser's install prompt. Resolves to whether the user accepted. */
	async function promptInstall() {
		const event = deferredPrompt.value;
		if (!event) return false;
		deferredPrompt.value = null; // a prompt event can be used once
		await event.prompt();
		const { outcome } = await event.userChoice;
		return outcome === "accepted";
	}

	return { canInstall, needsInstructions, promptInstall };
}
