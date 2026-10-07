import { createRouter, createMemoryHistory } from "vue-router";

// FAC Chat's named routes (src/router/index.js). Importing that module would pull every view into
// the widget bundle, so the names live here; panel.spec.js fails when the two drift apart.
const NAMED_ROUTES = [
	["chat", "/chat"],
	["chat-session", "/chat/:sessionId"],
	["knowledge", "/knowledge"],
	["agents", "/agents"],
	["agent-builder", "/agents/:id"],
	["analytics", "/analytics"],
	["settings-profile", "/settings/profile"],
	["settings-appearance", "/settings/appearance"],
	["settings-privacy", "/settings/privacy"],
	["MyTickets", "/settings/my-tickets"],
	["settings-routing", "/settings/routing"],
	["SettingsConnections", "/settings/connections"],
	["settings-memory", "/settings/memory"],
	["settings-users", "/settings/users"],
	["settings-packs", "/settings/packs"],
	["settings-my-packs", "/settings/my-packs"],
	["settings-billing", "/settings/billing"],
	["settings-workspace", "/settings/workspace"],
];

const Blank = { render: () => null };

/**
 * Shared components push FAC Chat routes (billing, workflow builder). In Desk
 * there is no FAC Chat router, so every navigation opens FAC Chat instead.
 */
export function createRouterShim() {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			...NAMED_ROUTES.map(([name, path]) => ({ name, path, component: Blank })),
			{ path: "/:rest(.*)*", component: Blank },
		],
	});
	router.beforeEach((to) => {
		if (to.fullPath === "/") return true;
		window.open(`/copilot${to.fullPath}`, "_blank", "noopener");
		return false;
	});
	return router;
}
