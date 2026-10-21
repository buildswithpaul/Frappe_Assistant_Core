import { ref } from "vue";
import { api } from "@/api/client";
import { fieldPlacementTarget } from "./customisation";

/**
 * Where the Custom Field an approval card is about to add will appear on its form: the server's
 * plain-language sentence and whether the spot is hidden. Stays null for any other write and when
 * the fetch fails, so a failed lookup never blocks the card.
 */
export function useFieldPlacement(getBlock) {
	const placement = ref(null);

	async function load() {
		const block = getBlock();
		const target = fieldPlacementTarget(block.tool_name, block.input);
		if (!target) return;
		try {
			const found = await api.tools.fieldPlacement(target.doctype, target.insertAfter, target.fieldtype);
			placement.value = found?.sentence ? { sentence: found.sentence, warning: Boolean(found.warning) } : null;
		} catch {
			placement.value = null;
		}
	}

	load();

	return placement;
}
