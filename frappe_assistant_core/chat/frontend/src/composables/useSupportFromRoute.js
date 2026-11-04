import { watch } from "vue";

const MODES = { 1: "feedback", issue: "issue" };

/**
 * `/chat?feedback=1` opens Help & Feedback on Give feedback (`feedback=issue` on Report an
 * issue) — a Spotlight's button can only follow a route, and the modal has no route of its own.
 * Strips the query so a refresh cannot reopen it.
 */
export function useSupportFromRoute({ route, router, supportStore }) {
	function apply(value) {
		if (value === undefined) return;
		const mode = typeof value === "string" ? MODES[value] : undefined;
		if (mode) supportStore.open({ mode });
		router.replace({
			path: route.path,
			query: { ...route.query, feedback: undefined },
			hash: route.hash,
		});
	}
	watch(() => route.query.feedback, apply, { immediate: true });
}
