/**
 * The drawer tab a person last chose, per kind of tool call, so someone who reads Raw is not sent
 * back to Summary on every block. Kept in this browser only.
 */
import { ref } from "vue";

const KEY = "fac-chat:tool-tab:";

function stored(kind) {
	try {
		return window.localStorage.getItem(KEY + kind);
	} catch {
		// Storage can be blocked (a private window): the default tab is used.
		return null;
	}
}

export function useRememberedTab(kind, tabs) {
	const saved = stored(kind);
	const tab = ref(tabs.includes(saved) ? saved : tabs[0]);

	function choose(next) {
		tab.value = next;
		try {
			window.localStorage.setItem(KEY + kind, next);
		} catch {
			// Not remembered; the choice still holds for this block.
		}
	}

	return { tab, choose };
}
