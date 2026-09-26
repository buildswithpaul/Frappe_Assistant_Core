import { onMounted, watch } from "vue";

import { readHandoff } from "@/utils/sessionHandoff";

/**
 * Initialize ChatView on mount: hydrate or load sessions, load suggestions/models
 * (staggered to avoid Gunicorn callback deadlock with AR's MCP list_prompts), handle
 * widget handoff via localStorage, load session from route, and apply deep-link redirects
 * (?tab=billing, ?success). Also watches the route sessionId and loads messages on change.
 *
 * IMPORTANT: calls must be staggered — AR's list_prompts calls BACK to this FACO site
 * (MCP callback), so a Gunicorn worker must be free. Firing all at once causes deadlock.
 *
 * @param {object} stores - { chatStore, userStore, modelStore, suggestionStore }
 * @param {object} routing - { route, router }
 * @param {object} state - { registrationStatus, isUserSetupComplete }
 */
export function useChatViewInit(stores, routing, state) {
	const { chatStore, userStore, modelStore, suggestionStore } = stores;
	const { route, router } = routing;
	const { registrationStatus, isUserSetupComplete } = state;

	onMounted(async () => {
		// User store already initialized in App.vue (single initialize_spa call)
		if (registrationStatus.value === "ready" && isUserSetupComplete.value) {
			// Consume pre-fetched sessions from initialize_spa (no API call)
			const initialSessions = userStore.getAndClearInitialSessions();
			if (initialSessions) {
				chatStore.hydrateSessions(initialSessions);
			} else {
				await chatStore.loadSessions();
			}

			// Load suggestions and models in background (non-blocking).
			// Stagger to free a Gunicorn worker for AR's MCP callback.
			suggestionStore.loadSuggestions({});
			setTimeout(() => modelStore.loadModels(), 500);

			// Widget handoff: if expand button stored an active session, route to it.
			// sessionStorage scopes the hand-off to this tab so other tabs don't
			// inherit the session id (cross-tab continuity is not a use case), and
			// the stamped owner keeps it from surviving into a different login.
			const activeSessionFromWidget = readHandoff(
				"faco_active_session",
				userStore.user
			);
			if (activeSessionFromWidget && !route.params.sessionId) {
				sessionStorage.removeItem("faco_active_session");
				router.push(`/chat/${activeSessionFromWidget}`);
				return;
			}

			if (route.params.sessionId) {
				await chatStore.loadMessages(route.params.sessionId);
				// If this conversation has a pending HITL pause that survived a
				// disconnect or worker restart, restore the InteractionCard so the
				// user can finish where they left off. Best-effort: the store
				// action swallows errors so a failed hydrate doesn't break mount.
				chatStore.hydratePendingInterrupt(route.params.sessionId);
			}
		}

		// Deep-link: checkout return / billing redirect from widget (preserves
		// pre-route-migration behaviour where ?tab=billing / ?success lands on billing).
		// The rest of the query rides along: the app-level checkout-return
		// handler still needs its markers, and removes them itself.
		const { tab, ...rest } = route.query;
		if ("success" in route.query || tab === "billing") {
			router.push({ path: "/settings/billing", query: rest });
		}
	});

	// Watch for route changes
	watch(
		() => route.params.sessionId,
		async (newSessionId) => {
			if (newSessionId) {
				await chatStore.loadMessages(newSessionId);
				chatStore.hydratePendingInterrupt(newSessionId);
			}
		}
	);
}
