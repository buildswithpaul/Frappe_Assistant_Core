import { ref } from "vue";
import { api } from "@/api/client";
import { goesLiveFields } from "./customisation";
import { flattenInput, isCodeField } from "./helpers";

/**
 * Current stored values of the code fields an update_document call is about to change, so the
 * card can diff old against new, plus the code an update switches on, so the user sees what
 * goes live. `current` stays null for any other tool and when the fetch fails, and the card then
 * shows the new code alone; `failed` tells a failed fetch apart from one still in flight, and
 * `loading` is true while code that goes live is still being fetched.
 */
export function useCurrentCode(getBlock) {
	const current = ref(null);
	const failed = ref(false);
	const loading = ref(false);

	async function load() {
		const block = getBlock();
		if (!block.input) return;
		const live = goesLiveFields(block.tool_name, block.input);
		if (block.tool_name !== "update_document" && !live.length) return;
		const flat = flattenInput(block.input);
		const { doctype, name } = flat;
		if (typeof doctype !== "string" || typeof name !== "string") return;
		const changed = Object.keys(flat).filter((k) => isCodeField(k, doctype) && typeof flat[k] === "string");
		const fields = [...new Set([...changed, ...live])];
		if (!fields.length) return;
		loading.value = live.length > 0;
		try {
			current.value = await api.tools.currentCode(doctype, name, fields);
		} catch {
			current.value = null;
			failed.value = true;
		} finally {
			loading.value = false;
		}
	}

	load();

	return { current, failed, loading };
}
