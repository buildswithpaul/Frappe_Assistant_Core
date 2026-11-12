import { describe, expect, it } from "vitest";
import {
	availablePowers,
	emptyState,
	liveTips,
	parseState,
	pickDailyTip,
	progressOf,
	safeRoute,
	storySlides,
	tipContent,
	unseenStory,
} from "./discoveryRules";

const tip = (id, extra = {}) => ({ id, display_style: "tip", title: "Did you know?", message: id, ...extra });
const known = { ...emptyState(), first_day: "2026-11-01" };

describe("parseState", () => {
	it("keeps only known keys, ids and dates", () => {
		const state = parseState({
			seen: ["agents", 3, "", "agents"],
			used: ["x".repeat(141), "pages"],
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
	it("keeps tips only, drops dismissed ones and ones about a used feature, high priority first", () => {
		const tips = liveTips(
			[
				tip("a", { feature: "agents" }),
				tip("b", { dismissed: true }),
				{ id: "m", display_style: "modal" },
				tip("c", { priority: "low" }),
				tip("d", { priority: "high" }),
			],
			{ used: ["agents"] }
		);
		expect(tips.map((t) => t.id)).toEqual(["d", "c"]);
	});

	it("uses the store's dismissal check, which includes local dismissals", () => {
		expect(liveTips([tip("a")], { isDismissed: () => true })).toEqual([]);
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

	it("a new day prefers a different tip, and falls back to the same one when it is the only one", () => {
		const state = { ...known, tip: { id: "a", date: "2026-11-11" } };
		expect(pickDailyTip({ tips: [tip("a"), tip("b")], state, today }).tip.id).toBe("b");
		expect(pickDailyTip({ tips: [tip("a")], state, today }).tip.id).toBe("a");
	});
});

describe("unseenStory", () => {
	const story = (id, extra = {}) => ({ id, display_style: "story", title: id, ...extra });

	it("the first story not watched and not dismissed", () => {
		const list = [story("s1", { dismissed: true }), story("s2"), story("s3")];
		expect(unseenStory(list, { seen: ["s2"] }).id).toBe("s3");
		expect(unseenStory([tip("t")])).toBeNull();
	});
});

describe("storySlides", () => {
	it("reads AR's slides, keeping an action only with a safe route", () => {
		const slides = storySlides({
			id: "s",
			slides: [
				{ title: "One", message: "m", media_url: "https://x/a.png" },
				{ title: "Two", action_label: "Try", action_route: "/agents" },
				{ title: "Three", action_label: "Bad", action_route: "https://evil.example" },
				{ message: "no title" },
			],
		});
		expect(slides.map((s) => s.title)).toEqual(["One", "Two", "Three"]);
		expect(slides[0].media).toEqual({ url: "https://x/a.png", type: "image", alt: "" });
		expect(slides[1].action).toEqual({ label: "Try", route: "/agents" });
		expect(slides[2].action).toBeNull();
	});

	it("a slide with no picture shows its feature's moving preview, AR's own picture first", () => {
		const slides = storySlides({
			id: "s",
			slides: [
				{ title: "A", feature: "agents" },
				{ title: "B", feature: "agents", media_url: "https://x/b.png" },
				{ title: "C", feature: "unknown" },
			],
		});
		expect(slides.map((s) => s.media)).toEqual([
			{ art: "feature", feature: "agents" },
			{ url: "https://x/b.png", type: "image", alt: "" },
			null,
		]);
	});

	it("a story without slides plays as one slide", () => {
		expect(storySlides({ id: "s", title: "New", message: "Hello" })).toEqual([
			{ title: "New", message: "Hello", media: null, action: null },
		]);
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

	it("a tip's pop-up uses AR's words, and the feature's own preview when AR sent no picture", () => {
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
