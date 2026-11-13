import { describe, expect, it } from "vitest";
import {
	availablePowers,
	emptyState,
	liveTips,
	parseState,
	pickDailyTip,
	powerColor,
	progressOf,
	ringSegments,
	safeRoute,
	tipContent,
} from "./discoveryRules";

const tip = (id, extra = {}) => ({ id, title: "Did you know?", message: id, ...extra });
const known = { ...emptyState(), first_day: "2026-11-01" };

describe("parseState", () => {
	it("keeps only known keys, ids and dates", () => {
		const state = parseState({
			seen: ["agents", 3, "", "agents"],
			used: ["x".repeat(141), "pages"],
			tips_dismissed: ["agents-routine-work", 5],
			coach_done: "yes",
			tip: { id: "t1", date: "12/11/2026" },
			tip_hidden_on: "2026-11-12",
			first_day: "2026-11-01",
			extra: "dropped",
		});
		expect(state).toEqual({
			...emptyState(),
			seen: ["agents"],
			used: ["pages"],
			tips_dismissed: ["agents-routine-work"],
			tip_hidden_on: "2026-11-12",
			first_day: "2026-11-01",
		});
	});

	it("reads anything that is not an object as empty", () => {
		expect(parseState(null)).toEqual(emptyState());
		expect(parseState("{}")).toEqual(emptyState());
	});
});

describe("liveTips", () => {
	it("drops a tip the user asked never to see again, and one about a feature they already use", () => {
		const tips = liveTips([tip("a", { feature: "agents" }), tip("b"), tip("c", { feature: "pages" })], {
			used: ["agents"],
			dismissed: ["b"],
		});
		expect(tips.map((t) => t.id)).toEqual(["c"]);
	});
});

describe("pickDailyTip", () => {
	const today = "2026-11-12";

	it("never on day one, FAC's first day with the user, or a day the user pressed ×", () => {
		const tips = [tip("a")];
		expect(pickDailyTip({ tips, state: known, today, dayOne: true }).tip).toBeNull();
		expect(pickDailyTip({ tips, state: { ...known, first_day: today }, today }).tip).toBeNull();
		expect(pickDailyTip({ tips, state: { ...known, tip_hidden_on: today }, today }).tip).toBeNull();
	});

	it("picks once a day and remembers it", () => {
		const { tip: picked, state } = pickDailyTip({ tips: [tip("a"), tip("b")], state: known, today });
		expect(picked.id).toBe("a");
		expect(state.tip).toEqual({ id: "a", date: today });
		const again = pickDailyTip({ tips: [tip("b"), tip("a")], state, today });
		expect(again.tip.id).toBe("a");
		expect(again.state).toBe(state);
	});

	it("today's tip gone (used or dismissed) means no other tip today", () => {
		const state = { ...known, tip: { id: "a", date: today } };
		expect(pickDailyTip({ tips: [tip("b")], state, today }).tip).toBeNull();
	});

	it("a new day moves to the next tip and goes round, so every tip gets its turn", () => {
		const order = ["a", "b", "c"];
		const tips = order.map((id) => tip(id));
		const seen = [];
		let state = known;
		for (const day of ["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"]) {
			const picked = pickDailyTip({ tips, state, today: day, order });
			seen.push(picked.tip.id);
			state = picked.state;
		}
		expect(seen).toEqual(["a", "b", "c", "a"]);
	});

	it("skips past a tip that is gone, and keeps the only one left", () => {
		const order = ["a", "b", "c"];
		const yesterdayB = { ...known, tip: { id: "b", date: "2026-11-11" } };
		expect(pickDailyTip({ tips: [tip("a"), tip("c")], state: yesterdayB, today, order }).tip.id).toBe("c");
		const yesterdayC = { ...known, tip: { id: "c", date: "2026-11-11" } };
		expect(pickDailyTip({ tips: [tip("a"), tip("b")], state: yesterdayC, today, order }).tip.id).toBe("a");
		const onlyA = { ...known, tip: { id: "a", date: "2026-11-11" } };
		expect(pickDailyTip({ tips: [tip("a")], state: onlyA, today, order }).tip.id).toBe("a");
	});
});

describe("availablePowers and progressOf", () => {
	const caps = {
		discovery: {
			progress_enabled: true,
			powers: [
				{ id: "setup", label: "Set up FAC" },
				{ id: "ask", label: "Ask your data" },
				{ id: "agents", label: "Agents", try_route: "/agents?tab=marketplace" },
				{ id: "knowledge", label: "Knowledge" },
				{ id: "mystery", label: "Unknown to the site" },
				{ id: "ask", label: "Duplicate" },
			],
		},
	};

	it("keeps AR's order, drops unknown ids, duplicates and features this site has off", () => {
		const powers = availablePowers(caps, { workflowsEnabled: true, memoryEnabled: false });
		expect(powers.map((p) => p.id)).toEqual(["setup", "ask", "agents"]);
		expect(powers[2].tryRoute).toBe("/agents?tab=marketplace");
	});

	it("nothing when AR sends no discovery block or switches progress off", () => {
		expect(availablePowers({})).toEqual([]);
		expect(availablePowers({ discovery: { ...caps.discovery, progress_enabled: false } })).toEqual([]);
	});

	it("starts at 1 (setup counts) and names the next power to try", () => {
		const powers = availablePowers(caps, { workflowsEnabled: true, memoryEnabled: true });
		expect(progressOf(powers, [])).toMatchObject({ done: 1, total: 4, next: { id: "ask" } });
		expect(progressOf(powers, ["ask"])).toMatchObject({ done: 2, next: { id: "agents" } });
	});
});

describe("safeRoute and tipContent", () => {
	it("allows only routes inside FAC Chat", () => {
		expect(safeRoute("/agents")).toBe("/agents");
		for (const bad of ["//evil", "/\\evil", "https://x", "/a b", null]) expect(safeRoute(bad)).toBeNull();
	});

	it("a tip's pop-up uses the tip's words, and the feature's own moving preview", () => {
		const content = tipContent(tip("t", { feature: "agents", action_label: "Show me", action_route: "/agents" }));
		expect(content).toMatchObject({
			kind: "tip",
			feature: "agents",
			title: "Did you know?",
			body: "t",
			media: { art: "feature", feature: "agents" },
			primary: { label: "Show me", route: "/agents" },
		});
		expect(tipContent(tip("t", { action_route: "javascript:x" })).primary.route).toBeNull();
	});
});

describe("powerColor and ringSegments", () => {
	const powers = ["setup", "ask", "templates", "knowledge", "pages", "agents", "extra"].map((id) => ({ id }));

	it("gives each power its own colour, going round after six", () => {
		expect(powers.map((_, i) => powerColor(i))).toEqual([
			"var(--ql-power-1)",
			"var(--ql-power-2)",
			"var(--ql-power-3)",
			"var(--ql-power-4)",
			"var(--ql-power-5)",
			"var(--ql-power-6)",
			"var(--ql-power-1)",
		]);
	});

	it("splits the ring into one arc per power, in order, with a gap between arcs", () => {
		const segs = ringSegments(powers.slice(0, 6), ["pages"], { circ: 120, gap: 4 });
		expect(segs.map((s) => [s.id, s.done])).toEqual([
			["setup", true],
			["ask", false],
			["templates", false],
			["knowledge", false],
			["pages", true],
			["agents", false],
		]);
		expect(segs[0]).toMatchObject({ dasharray: "16 104", dashoffset: -2, color: "var(--ql-power-1)" });
		expect(segs[4]).toMatchObject({ dashoffset: -82, color: "var(--ql-power-5)" });
	});

	it("draws nothing for an empty list", () => {
		expect(ringSegments([], [], { circ: 120, gap: 4 })).toEqual([]);
	});
});
