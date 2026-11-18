import { __ } from "@/utils/i18n";
import { featureById, previewContent } from "./featureCatalog";

/**
 * Your FAC: the powers whose Try explains first. Many users do not know what asking their data or
 * a Page does, so Try shows a card (what it is, examples) with a choice: FAC asks a question for
 * them in a new chat, or they write their own. Either way the power ticks once they have asked.
 */
export const EXPLAINED_POWERS = ["ask", "pages"];

// Used when Home has no starter question for this user yet.
const FALLBACK_QUESTION = () => __("Who are my top 5 customers by sales this year?");

/** The card for a power, in the shape SpotlightModal renders; null for a power that does not explain. */
export function explainContent(id) {
	if (id === "ask") {
		return {
			kind: "power",
			id: "power-ask",
			power: "ask",
			eyebrow: __("FAC can ask one for you, or ask your own"),
			title: __("Ask your data in plain words"),
			body: __(
				"Type a question the way you would ask a colleague. FAC looks it up in your ERPNext data, with your own permissions, and answers in seconds."
			),
			highlights: [
				__("Who owes us the most, and since when?"),
				__("Top 10 customers by sales this month"),
				__("Which items are below reorder level?"),
			],
			media: null,
			primary: { label: __("Ask one for me") },
			secondary: { label: __("I'll ask my own") },
		};
	}
	if (id === "pages") {
		return {
			...previewContent(featureById("pages")),
			kind: "power",
			id: "power-pages",
			power: "pages",
			eyebrow: __("FAC can make one for you, or write your own"),
			primary: { label: __("Make a Page for me") },
			secondary: { label: __("I'll write my own") },
		};
	}
	return null;
}

/**
 * The question a power's button asks. Ask uses one of the user's own Home starters (Home picks those
 * for the user's role, so a stock user is not asked about receivables): a short lookup (the Find it
 * card) first, then a See it one, so the first answer is quick and plain.
 */
export function questionFor(id, suggestions = []) {
	if (id === "pages") return featureById("pages").tryIt.prompt();
	const starters = (suggestions || []).filter((s) => s && s.source !== "page" && s.description);
	const starter =
		starters.find((s) => s.kind === "find") || starters.find((s) => s.kind === "see") || starters[0];
	return starter ? starter.description : FALLBACK_QUESTION();
}
