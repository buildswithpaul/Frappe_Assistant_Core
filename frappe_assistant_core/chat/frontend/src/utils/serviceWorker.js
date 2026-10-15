// Registers FAC Chat's service worker, which makes the SPA installable and opens
// it fast. Served at /copilot/sw.js (chat/service_worker.py) so its scope covers
// the SPA's pages. Not registered by the dev server: Vite serves no worker there.
export function registerServiceWorker() {
	if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
	window.addEventListener("load", () => {
		navigator.serviceWorker.register("/copilot/sw.js", { scope: "/copilot/" }).catch(() => {
			// An unregistered worker only costs the install option and fast start.
		});
	});
}
