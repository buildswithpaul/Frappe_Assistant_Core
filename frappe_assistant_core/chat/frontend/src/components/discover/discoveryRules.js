/**
 * Did you know tips and Your FAC progress. Pure: no Vue, no network.
 *
 * Tips ship with FAC (dailyTips.js), one set per release; the Your FAC powers come from AR's
 * capabilities.discovery. This file decides when: a tip once a day, taking turns, until its feature
 * is used; never on day one; the ring from real usage.
 */
import { __ } from "@/utils/i18n";
import { featureById } from "./featureCatalog";

/** The ids the site knows how to check. A power or tip feature AR sends with any other id is ignored. */
export const POWER_IDS = ["setup", "ask", "templates", "knowledge", "pages", "agents"];

/** Which userStore flag must be on for a power to be offered (null = always). */
const POWER_CAPABILITY = { knowledge: "memoryEnabled", agents: "workflowsEnabled" };

export const LIST_KEYS = ["seen", "used", "celebrated", "tips_dismissed"];
const LIST_MAX = 50;
const ID_MAX = 140;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function emptyState() {
	return {
		seen: [],
		used: [],
		celebrated: [],
		tips_dismissed: [],
		coach_done: false,
		tip: null,
		tip_hidden_on: null,
		first_day: null,
	};
}

const dateOrNull = (v) => (typeof v === "string" && ISO_DATE.test(v) ? v : null);
const validId = (v) => typeof v === "string" && v.length > 0 && v.length <= ID_MAX;

/** Same rules as the server's parse_discovery_state, so both sides agree on what is stored. */
export function parseState(raw) {
	const state = emptyState();
	if (!raw || typeof raw !== "object") return state;
	for (const key of LIST_KEYS) {
		const list = Array.isArray(raw[key]) ? raw[key].filter(validId) : [];
		state[key] = [...new Set(list)].slice(-LIST_MAX);
	}
	state.coach_done = raw.coach_done === true;
	const tip = raw.tip;
	if (tip && validId(tip.id) && dateOrNull(tip.date)) state.tip = { id: tip.id, date: tip.date };
	state.tip_hidden_on = dateOrNull(raw.tip_hidden_on);
	state.first_day = dateOrNull(raw.first_day);
	return state;
}

/** The tips still live for this user: not "never again", and not about a feature they already use. */
export function liveTips(tips, { used = [], dismissed = [] } = {}) {
	return (tips || []).filter((t) => !dismissed.includes(t.id) && !(t.feature && used.includes(t.feature)));
}

/**
 * Today's tip, at most one a day. Keeps today's tip if it is still live; otherwise the next live
 * tip after the last day's in `order`, going round after the last, so every tip gets its turn.
 * Returns `{ tip, state }`: the tip to show (or null) and the state to store.
 */
export function pickDailyTip({ tips, state, today, dayOne, order = tips.map((t) => t.id) }) {
	if (dayOne || state.first_day === today || state.tip_hidden_on === today) return { tip: null, state };
	const current = state.tip;
	if (current && current.date === today) {
		return { tip: tips.find((t) => t.id === current.id) || null, state };
	}
	if (!tips.length) return { tip: null, state };
	const last = current ? order.indexOf(current.id) : -1;
	const next = (last >= 0 && tips.find((t) => order.indexOf(t.id) > last)) || tips[0];
	return { tip: next, state: { ...state, tip: { id: next.id, date: today } } };
}

/** A route inside FAC Chat: starts with one "/", no whitespace. */
export function safeRoute(route) {
	return typeof route === "string" && /^\/(?![/\\])/.test(route) && !/\s/.test(route) ? route : null;
}

/** The Your FAC powers AR listed, in AR's order, keeping only ids the site can check and features it has. */
export function availablePowers(capabilities, flags = {}) {
	const discovery = capabilities && capabilities.discovery;
	if (!discovery || discovery.progress_enabled === false || !Array.isArray(discovery.powers)) return [];
	const seen = new Set();
	return discovery.powers
		.filter((p) => p && POWER_IDS.includes(p.id) && p.label && !seen.has(p.id) && seen.add(p.id))
		.filter((p) => !POWER_CAPABILITY[p.id] || flags[POWER_CAPABILITY[p.id]] === true)
		.map((p) => ({
			id: p.id,
			label: String(p.label),
			description: p.description ? String(p.description) : "",
			tryRoute: safeRoute(p.try_route),
		}));
}

/** Setup always counts: anyone who sees the ring has set FAC up. */
export function isPowerUsed(id, used) {
	return id === "setup" || used.includes(id);
}

export function progressOf(powers, used) {
	const done = powers.filter((p) => isPowerUsed(p.id, used)).length;
	return { done, total: powers.length, next: powers.find((p) => !isPowerUsed(p.id, used)) || null };
}

/** Each power's colour, by its place in AR's list: --ql-power-1 … --ql-power-6, then round again. */
export function powerColor(index) {
	return `var(--ql-power-${(index % 6) + 1})`;
}

/**
 * The Your FAC ring as one arc per power, in list order: done arcs take the power's colour,
 * the rest stay grey. `circ` is the circle's length, `gap` the space between arcs.
 */
export function ringSegments(powers, used, { circ, gap }) {
	const step = circ / (powers.length || 1);
	const length = Math.max(step - gap, 0);
	return powers.map((p, i) => ({
		id: p.id,
		done: isPowerUsed(p.id, used),
		color: powerColor(i),
		dasharray: `${length} ${circ - length}`,
		dashoffset: -(i * step + gap / 2),
	}));
}

/**
 * The "Show me" pop-up for a tip, in the shape SpotlightModal renders. A tip without its own
 * picture gets the moving preview of its feature, when the site has one.
 */
export function tipContent(tip) {
	const feature = tip.feature && featureById(tip.feature);
	let media = tip.media_url ? { url: tip.media_url, type: tip.media_type || "image", alt: tip.media_alt || "" } : null;
	if (!media && feature) media = { art: "feature", feature: feature.id };
	const route = safeRoute(tip.action_route);
	return {
		kind: "tip",
		id: tip.id,
		feature: feature ? feature.id : null,
		eyebrow: tip.eyebrow || __("Did you know?"),
		title: tip.title || __("Did you know?"),
		body: tip.message || "",
		highlights: Array.isArray(tip.highlights) ? tip.highlights : [],
		media,
		primary: { label: tip.action_label || __("Give it a try"), route },
		secondary: { label: __("Maybe later") },
	};
}
