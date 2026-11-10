/**
 * Feature discovery: what FAC shows on Home so people find Agents, Knowledge,
 * Pages and Prompt templates at their own pace. Pure: no Vue, no network.
 *
 * The rule behind it: chat stays chat. Features are shown here, never pushed
 * inside a conversation. The "Want to try it?" question only comes after the
 * user clicked to see a feature.
 */
import { __ } from "@/utils/i18n";

export const DISCOVERY_KEY = (user) => `fac_discovery:${user}`;
export const TIP_DAYS = 7;

/**
 * One entry per feature. `capability` names a userStore flag that must be true
 * (null = always available). `tryIt` says where "Give it a try" goes: a route,
 * or `templates` to open the prompt-template browser.
 */
export const FEATURES = [
	{
		id: "agents",
		capability: "workflowsEnabled",
		routePrefix: "/agents",
		title: () => __("Agents"),
		blurb: () => __("Routine work, done on a schedule"),
		popupTitle: () => __("Agents do routine work for you"),
		popupBody: () =>
			__(
				"An agent runs on a schedule or when something happens in ERPNext, and does the steps you would otherwise do by hand."
			),
		uses: () => [
			__("Email me overdue invoices every Monday"),
			__("Tell the buyer when stock drops below reorder level"),
			__("Check every new purchase invoice against its PO"),
		],
		note: () => __("Start from a ready-made template"),
		tryIt: { route: "/agents?tab=marketplace" },
	},
	{
		id: "knowledge",
		capability: "memoryEnabled",
		routePrefix: "/knowledge",
		title: () => __("Knowledge"),
		blurb: () => __("Answers from your own files"),
		popupTitle: () => __("Answers from your own documents"),
		popupBody: () =>
			__("Upload price lists, policies or SOPs. FAC answers from them and shows the page it used."),
		uses: () => [
			__("What is our price for this item?"),
			__("What does our leave policy say about carry-over?"),
			__("Which steps does our returns SOP list?"),
		],
		note: () => __("PDF, Markdown or text files"),
		tryIt: { route: "/knowledge" },
	},
	{
		id: "pages",
		capability: null,
		routePrefix: "/pages",
		title: () => __("Pages"),
		blurb: () => __("Live reports from any answer"),
		popupTitle: () => __("Pages: live reports from any answer"),
		popupBody: () =>
			__(
				"Ask for numbers, then save the answer as a Page. FAC keeps it up to date, and you can download it as PDF."
			),
		uses: () => [
			__("A sales summary your team checks each morning"),
			__("Receivables by customer, ready for the Monday meeting"),
			__("A stock report you can share as PDF"),
		],
		note: () => __("FAC writes the question for you; you press send"),
		tryIt: { prompt: () => __("Show this month's sales by customer and save it as a Page.") },
	},
	{
		id: "templates",
		capability: null,
		routePrefix: null,
		title: () => __("Prompt templates"),
		blurb: () => __("Reuse your best questions"),
		popupTitle: () => __("Prompt templates: ask your best questions again"),
		popupBody: () =>
			__("Pick a saved question, fill in the blanks, and send. Pin the ones you use most."),
		uses: () => [
			__("A monthly sales review with the month as a blank"),
			__("A customer summary for any customer you name"),
			__("Your team's standard stock check"),
		],
		note: () => __("Also opens from the composer's + menu"),
		tryIt: { templates: true },
	},
];

export const FEATURE_IDS = FEATURES.map((f) => f.id);

export function featureById(id) {
	return FEATURES.find((f) => f.id === id) || null;
}

/** The features this user can use: each feature's capability flag must be true. */
export function availableFeatures(flags = {}) {
	return FEATURES.filter((f) => f.capability === null || flags[f.capability] === true);
}

/** Which feature a route belongs to, so visiting it counts as "opened". */
export function featureForPath(path) {
	const p = String(path || "");
	const hit = FEATURES.find((f) => f.routePrefix && (p === f.routePrefix || p.startsWith(`${f.routePrefix}/`)));
	return hit ? hit.id : null;
}

export function emptyState() {
	return { seen: [], dismissedTips: [], tip: null, rowHidden: false, coachDone: false };
}

/** Reads a stored state, keeping only known keys and types (storage can hold anything). */
export function parseState(raw) {
	const state = emptyState();
	if (!raw) return state;
	let data;
	try {
		data = JSON.parse(raw);
	} catch {
		return state;
	}
	if (!data || typeof data !== "object") return state;
	const ids = (list) => (Array.isArray(list) ? list.filter((id) => FEATURE_IDS.includes(id)) : []);
	state.seen = ids(data.seen);
	state.dismissedTips = ids(data.dismissedTips);
	state.rowHidden = data.rowHidden === true;
	state.coachDone = data.coachDone === true;
	const tip = data.tip;
	if (tip && FEATURE_IDS.includes(tip.id) && /^\d{4}-\d{2}-\d{2}$/.test(tip.since || "")) {
		state.tip = { id: tip.id, since: tip.since };
	}
	return state;
}

function daysBetween(fromIso, toIso) {
	const [y1, m1, d1] = fromIso.split("-").map(Number);
	const [y2, m2, d2] = toIso.split("-").map(Number);
	return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000);
}

/**
 * The weekly "Did you know?" tip. One feature per week, only one the user has
 * not tried, and a dismissed tip never comes back. Returns `{ tip, state }`:
 * `tip` is the feature id to show (or null) and `state.tip` is what to store.
 *
 * Within a tip's week the same tip stays; once the user tries the feature or
 * dismisses the tip, nothing shows until the week is over.
 */
export function pickTip({ state, candidates, today }) {
	const current = state.tip;
	if (current && daysBetween(current.since, today) < TIP_DAYS) {
		const showable = candidates.includes(current.id) && !state.dismissedTips.includes(current.id);
		return { tip: showable ? current.id : null, state };
	}
	const open = candidates.filter((id) => !state.dismissedTips.includes(id));
	if (!open.length) return { tip: null, state };
	// Rotate: the next open feature after last week's, so each gets a turn.
	const after = current ? FEATURE_IDS.indexOf(current.id) : -1;
	const next = open.find((id) => FEATURE_IDS.indexOf(id) > after) || open[0];
	return { tip: next, state: { ...state, tip: { id: next, since: today } } };
}

/** The "show first, then ask" pop-up, in the shape SpotlightModal renders. */
export function previewContent(feature) {
	return {
		kind: "feature",
		id: `feature-${feature.id}`,
		feature: feature.id,
		eyebrow: feature.note(),
		title: feature.popupTitle(),
		body: feature.popupBody(),
		highlights: feature.uses(),
		media: { art: "feature", feature: feature.id },
		primary: { label: __("Give it a try") },
		secondary: { label: __("Maybe later") },
	};
}

/** The first-login tour: where things are, not how every feature works. */
export const COACH_STOPS = [
	{
		selector: ".welcome-composer-slot",
		title: () => __("Ask anything here"),
		text: () => __("Type a question about your business, in plain words."),
		place: "below",
	},
	{
		selector: ".ny",
		title: () => __("FAC watches for you"),
		text: () => __("These cards show things that need your attention, from your own data."),
		place: "below",
	},
	{
		selector: ".nav-rail",
		title: () => __("Everything else lives here"),
		text: () => __("Knowledge, Agents, Pages and more. Explore them whenever you like."),
		place: "right",
	},
];
