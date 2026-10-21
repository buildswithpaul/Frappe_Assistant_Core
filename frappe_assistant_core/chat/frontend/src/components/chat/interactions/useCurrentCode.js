import { ref } from "vue";
import { api } from "@/api/client";
import { flattenInput, isCodeKey } from "./helpers";

/**
 * Current stored values of the code fields an update_document call is about to change, so the
 * card can diff old against new. Stays null for any other tool and when the fetch fails, and
 * the card then shows the new code alone.
 */
export function useCurrentCode(getBlock) {
	const current = ref(null);

	async function load() {
		const block = getBlock();
		if (block.tool_name !== "update_document" || !block.input) return;
		const flat = flattenInput(block.input);
		const { doctype, name } = flat;
		if (typeof doctype !== "string" || typeof name !== "string") return;
		const fields = Object.keys(flat).filter((k) => isCodeKey(k) && typeof flat[k] === "string");
		if (!fields.length) return;
		try {
			current.value = await api.tools.currentCode(doctype, name, fields);
		} catch {
			current.value = null;
		}
	}

	load();

	return current;
}
