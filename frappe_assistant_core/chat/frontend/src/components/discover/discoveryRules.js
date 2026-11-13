/**
 * Your FAC progress. Pure: no Vue, no network.
 *
 * The Your FAC powers come from AR's capabilities.discovery; this file keeps the stored state
 * clean and works out the ring from real usage.
 */

/** The ids the site knows how to check. A power AR sends with any other id is ignored. */
export const POWER_IDS = ["setup", "ask", "templates", "knowledge", "pages", "agents"];

/** Which userStore flag must be on for a power to be offered (null = always). */
const POWER_CAPABILITY = { knowledge: "memoryEnabled", agents: "workflowsEnabled" };

export const LIST_KEYS = ["seen", "used", "celebrated"];
const LIST_MAX = 50;
const ID_MAX = 140;

export function emptyState() {
	return {
		seen: [],
		used: [],
		celebrated: [],
		coach_done: false,
	};
}

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
	return state;
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
