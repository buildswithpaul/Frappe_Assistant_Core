import { watch } from "vue";

export const MAX_PROMPT_CHARS = 2000;

/**
 * `/chat?prompt=…` pre-fills the composer of a new chat — Spotlight's "Try it"
 * links land here. Never sends, and strips the query so a refresh cannot
 * re-fill the draft.
 */
export function usePromptFromRoute({ route, router, pendingPrompt, isNewChat }) {
	function apply(prompt) {
		if (typeof prompt !== "string" || !prompt.trim() || !isNewChat()) return;
		pendingPrompt.value = prompt.slice(0, MAX_PROMPT_CHARS);
		router.replace({ ...route, query: { ...route.query, prompt: undefined } });
	}
	watch(() => route.query.prompt, apply, { immediate: true });
}
