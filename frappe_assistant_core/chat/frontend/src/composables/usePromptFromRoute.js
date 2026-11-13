import { watch } from "vue";

export const MAX_PROMPT_CHARS = 2000;

/**
 * `/chat?prompt=…` pre-fills the composer of a new chat — Spotlight's "Try it"
 * links land here. Never sends, and strips the query so a refresh cannot
 * re-fill the draft. `&page=<name>` also opens that FAC Page beside the chat,
 * as the Desk Pages gallery's Edit with FACO and Share links ask.
 */
export function usePromptFromRoute({ route, router, pendingPrompt, isNewChat, openPage }) {
	function apply(prompt) {
		// Always strip the prompt query param to prevent reloads from re-filling
		const hasPromptParam = typeof prompt === "string";
		const shouldApply = hasPromptParam && prompt.trim() && isNewChat();

		if (shouldApply) {
			pendingPrompt.value = prompt.slice(0, MAX_PROMPT_CHARS);
			const page = route.query.page;
			if (typeof page === "string" && page) openPage?.(page);
		}

		// Strip query param whether accepted or rejected
		if (hasPromptParam) {
			router.replace({
				path: route.path,
				query: { ...route.query, prompt: undefined, page: undefined },
				hash: route.hash,
			});
		}
	}
	watch(() => route.query.prompt, apply, { immediate: true });
}
