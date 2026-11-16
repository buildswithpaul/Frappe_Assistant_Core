import { __ } from "@/utils/i18n";

export const BRING_DATA_SOURCE = "bring_data";

// The "Bring your data in" starter. The server only says whether this user may see it
// (`bring_data_in` on the suggestions payload); the copy is built here so `__()` resolves
// in the user's language. `description` is the prompt a click sends, like every other tile.
export function bringDataStarter() {
	return {
		name: "bring_your_data",
		title: __("Bring your data in"),
		subtext: __("Import customers, items and opening balances from spreadsheets or Tally."),
		description: __(
			"I want to bring my data into ERPNext from my old system (spreadsheets or a Tally export). What do you need from me?"
		),
		source: BRING_DATA_SOURCE,
	};
}

// `tiles` with the starter appended when the server allows it.
export function withBringData(tiles, allowed) {
	return allowed ? [...tiles, bringDataStarter()] : tiles;
}
