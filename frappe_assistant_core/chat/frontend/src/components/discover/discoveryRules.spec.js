import { describe, expect, it } from "vitest";
import {
	availablePowers,
	emptyState,
	parseState,
	powerColor,
	progressOf,
	ringSegments,
	safeRoute,
} from "./discoveryRules";

describe("parseState", () => {
	it("keeps only known keys and ids; old tip fields are dropped", () => {
		const state = parseState({
			seen: ["agents", 3, "", "agents"],
			used: ["x".repeat(141), "pages"],
			coach_done: "yes",
			tip_hidden_on: "2026-11-12",
			first_day: "2026-11-01",
			extra: "dropped",
		});
		expect(state).toEqual({
			...emptyState(),
			seen: ["agents"],
			used: ["pages"],
		});
	});

	it("reads anything that is not an object as empty", () => {
		expect(parseState(null)).toEqual(emptyState());
		expect(parseState("{}")).toEqual(emptyState());
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

describe("safeRoute", () => {
	it("allows only routes inside FAC Chat", () => {
		expect(safeRoute("/agents")).toBe("/agents");
		for (const bad of ["//evil", "/\\evil", "https://x", "/a b", null]) expect(safeRoute(bad)).toBeNull();
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
