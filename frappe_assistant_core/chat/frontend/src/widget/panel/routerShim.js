import { createRouter, createMemoryHistory } from "vue-router";

/**
 * Shared components push FAC Chat routes (billing, workflow builder). In Desk
 * there is no FAC Chat router, so every navigation opens FAC Chat instead.
 */
export function createRouterShim() {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:rest(.*)*", component: { render: () => null } }],
	});
	router.beforeEach((to) => {
		if (to.fullPath === "/") return true;
		window.open(`/copilot${to.fullPath}`, "_blank", "noopener");
		return false;
	});
	return router;
}
