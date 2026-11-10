import { describe, expect, it } from "vitest";
import {
	FEATURE_IDS,
	availableFeatures,
	emptyState,
	featureForPath,
	parseState,
	pickTip,
	previewContent,
	featureById,
} from "./featureCatalog";

const ALL = ["agents", "knowledge", "pages", "templates"];

describe("availableFeatures", () => {
	it("leaves out Agents without workflows and Knowledge without memory", () => {
		expect(availableFeatures({}).map((f) => f.id)).toEqual(["pages", "templates"]);
		expect(availableFeatures({ workflowsEnabled: true, memoryEnabled: true }).map((f) => f.id)).toEqual(ALL);
	});
});

describe("featureForPath", () => {
	it("maps a feature's routes, and nothing else", () => {
		expect(featureForPath("/knowledge")).toBe("knowledge");
		expect(featureForPath("/agents/WF-1")).toBe("agents");
		expect(featureForPath("/pages/sales")).toBe("pages");
		expect(featureForPath("/agentsx")).toBe(null);
		expect(featureForPath("/chat")).toBe(null);
		expect(featureForPath(undefined)).toBe(null);
	});
});

describe("parseState", () => {
	it("falls back to an empty state on missing or broken storage", () => {
		expect(parseState(null)).toEqual(emptyState());
		expect(parseState("{not json")).toEqual(emptyState());
		expect(parseState("42")).toEqual(emptyState());
	});

	it("keeps only known feature ids and a well-formed tip", () => {
		const raw = JSON.stringify({
			seen: ["agents", "bogus", 7],
			dismissedTips: ["pages"],
			rowHidden: true,
			coachDone: "yes",
			tip: { id: "knowledge", since: "2026-11-02" },
		});
		expect(parseState(raw)).toEqual({
			seen: ["agents"],
			dismissedTips: ["pages"],
			rowHidden: true,
			coachDone: false,
			tip: { id: "knowledge", since: "2026-11-02" },
		});
		expect(parseState(JSON.stringify({ tip: { id: "knowledge", since: "soon" } })).tip).toBe(null);
	});
});

describe("pickTip", () => {
	const base = emptyState();

	it("starts a week with the first untried feature", () => {
		const { tip, state } = pickTip({ state: base, candidates: ["knowledge", "pages"], today: "2026-11-10" });
		expect(tip).toBe("knowledge");
		expect(state.tip).toEqual({ id: "knowledge", since: "2026-11-10" });
	});

	it("keeps the same tip for the rest of its week", () => {
		const state = { ...base, tip: { id: "knowledge", since: "2026-11-10" } };
		const r = pickTip({ state, candidates: ["knowledge", "pages"], today: "2026-11-16" });
		expect(r.tip).toBe("knowledge");
		expect(r.state).toBe(state);
	});

	it("shows nothing for the rest of the week once the tip is dismissed or the feature tried", () => {
		const state = { ...base, tip: { id: "knowledge", since: "2026-11-10" }, dismissedTips: ["knowledge"] };
		expect(pickTip({ state, candidates: ["knowledge", "pages"], today: "2026-11-12" }).tip).toBe(null);
		const tried = { ...base, tip: { id: "knowledge", since: "2026-11-10" } };
		expect(pickTip({ state: tried, candidates: ["pages"], today: "2026-11-12" }).tip).toBe(null);
	});

	it("moves to the next feature after a week, and a dismissed tip never comes back", () => {
		const state = { ...base, tip: { id: "knowledge", since: "2026-11-03" }, dismissedTips: ["knowledge"] };
		const r = pickTip({ state, candidates: ["agents", "knowledge", "pages"], today: "2026-11-10" });
		expect(r.tip).toBe("pages");
		expect(r.state.tip).toEqual({ id: "pages", since: "2026-11-10" });
		// After the last feature the rotation wraps to the start.
		const later = pickTip({ state: r.state, candidates: ["agents", "pages"], today: "2026-11-17" });
		expect(later.tip).toBe("agents");
	});

	it("shows nothing when every untried feature was dismissed", () => {
		const state = { ...base, dismissedTips: ["pages"] };
		expect(pickTip({ state, candidates: ["pages"], today: "2026-11-10" }).tip).toBe(null);
	});
});

describe("previewContent", () => {
	it("is the SpotlightModal shape: three uses and Give it a try / Maybe later", () => {
		for (const id of FEATURE_IDS) {
			const c = previewContent(featureById(id));
			expect(c.media).toEqual({ art: "feature", feature: id });
			expect(c.highlights).toHaveLength(3);
			expect(c.primary.label).toBe("Give it a try");
			expect(c.secondary.label).toBe("Maybe later");
		}
	});
});
