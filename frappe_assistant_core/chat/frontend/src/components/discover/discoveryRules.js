/**
 * Did you know tips, What's new stories and Your FAC progress. Pure: no Vue, no network.
 *
 * AR decides what and who: tips and stories are AR notifications (display_style "tip" / "story"),
 * powers come from capabilities.discovery. This file decides when: a tip once a day until its
 * feature is used, never on day one; a story until it is watched; the ring from real usage.
 */
import { __ } from "@/utils/i18n";
import { featureById } from "./featureCatalog";

/** The ids the site knows how to check. A power or tip feature AR sends with any other id is ignored. */
export const POWER_IDS = ["setup", "ask", "templates", "knowledge", "pages", "agents"];

/** Which userStore flag must be on for a power to be offered (null = always). */
const POWER_CAPABILITY = { knowledge: "memoryEnabled", agents: "workflowsEnabled" };

export const LIST_KEYS = ["seen", "used", "celebrated", "stories_seen"];
const LIST_MAX = 50;
const ID_MAX = 140;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const PRIORITY_RANK = { high: 0, normal: 1, low: 2 };

export function emptyState() {
	return {
		seen: [],
		used: [],
		celebrated: [],
		stories_seen: [],
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

const byPriority = (a, b) => (PRIORITY_RANK[a.priority] ?? 1) - (PRIORITY_RANK[b.priority] ?? 1);

/** Tips AR sent that are still live: not dismissed for good, and not about a feature already used. */
export function liveTips(notifications, { used = [], isDismissed = (n) => Boolean(n.dismissed) } = {}) {
	return (notifications || [])
		.filter((n) => n && n.display_style === "tip" && validId(n.id) && !isDismissed(n))
		.filter((n) => !(n.feature && used.includes(n.feature)))
		.sort(byPriority);
}

/**
 * Today's tip, at most one a day. Keeps today's tip if it is still live; otherwise picks the
 * highest-priority live tip, preferring a different one from the last day's. Returns
 * `{ tip, state }`: the notification to show (or null) and the state to store.
 */
export function pickDailyTip({ tips, state, today, dayOne }) {
	if (dayOne || state.first_day === today || state.tip_hidden_on === today) return { tip: null, state };
	const current = state.tip;
	if (current && current.date === today) {
		return { tip: tips.find((t) => t.id === current.id) || null, state };
	}
	if (!tips.length) return { tip: null, state };
	const next = tips.find((t) => !current || t.id !== current.id) || tips[0];
	return { tip: next, state: { ...state, tip: { id: next.id, date: today } } };
}

/** The first story AR sent that this user has not watched yet. */
export function unseenStory(notifications, { seen = [], isDismissed = (n) => Boolean(n.dismissed) } = {}) {
	return (
		(notifications || []).find(
			(n) => n && n.display_style === "story" && validId(n.id) && !isDismissed(n) && !seen.includes(n.id)
		) || null
	);
}

/** A route inside FAC Chat: starts with one "/", no whitespace. */
export function safeRoute(route) {
	return typeof route === "string" && /^\/(?![/\\])/.test(route) && !/\s/.test(route) ? route : null;
}

function slideFrom(s) {
	if (!s || typeof s !== "object" || !s.title) return null;
	return {
		title: String(s.title),
		message: s.message ? String(s.message) : "",
		media: s.media_url ? { url: s.media_url, type: s.media_type || "image", alt: s.media_alt || "" } : null,
		action: s.action_label && safeRoute(s.action_route) ? { label: s.action_label, route: s.action_route } : null,
	};
}

/** A story's slides; a story without `slides` plays as one slide made from its own fields. */
export function storySlides(story) {
	if (!story) return [];
	const slides = Array.isArray(story.slides) ? story.slides.map(slideFrom).filter(Boolean) : [];
	return slides.length ? slides : [slideFrom(story)].filter(Boolean);
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
