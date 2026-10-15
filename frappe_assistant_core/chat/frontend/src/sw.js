// FAC Chat service worker: makes the SPA installable, opens it fast, and shows
// an offline page when there is no connection. It never caches anything
// user-specific: the rendered /copilot page carries the user's boot data and
// CSRF token, so navigations always go to the network.
//
// Served at /copilot/sw.js by chat/service_worker.py, not from /assets/: a
// worker can only control pages under the path its script is served from.

import { cleanupOutdatedCaches, matchPrecache, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { CacheFirst } from "workbox-strategies";
import { ExpirationPlugin } from "workbox-expiration";

const SPA_BASE = "/assets/frappe_assistant_core/chat/spa/";
const OFFLINE_PAGE = `${SPA_BASE}offline.html`;

// What the first screen needs (the entry script, its static imports and CSS,
// fonts, icons and the offline page), injected at build time by vite-plugin-pwa.
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Every other build chunk, such as the diagram renderers or the workflow
// builder, is cached the first time it is used. File names carry a content
// hash, so a cached copy is never stale; the expiry only bounds the cache.
registerRoute(
	({ url }) => url.origin === self.location.origin && url.pathname.startsWith(`${SPA_BASE}assets/`),
	new CacheFirst({
		cacheName: "fac-chat-chunks",
		plugins: [new ExpirationPlugin({ maxEntries: 200, purgeOnQuotaError: true })],
	})
);

registerRoute(
	new NavigationRoute(
		async ({ request }) => {
			try {
				return await fetch(request);
			} catch {
				return (await matchPrecache(OFFLINE_PAGE)) || Response.error();
			}
		},
		// Only the SPA's own pages; Desk, /api and the rest of the site are untouched.
		{ allowlist: [/^\/copilot(\/|$)/] }
	)
);

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
