import { createMemoryHistory, createRouter } from "vue-router";

const Blank = { render: () => null };

/**
 * A memory-history router with a catch-all route, for specs that mount a component calling
 * `useRouter()`. Without a router plugin Vue warns that the injection is missing.
 */
export function testRouter(routes = [{ path: "/:rest(.*)*", component: Blank }]) {
	return createRouter({ history: createMemoryHistory(), routes });
}
