import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import RoutingPanel from "../RoutingPanel.vue";

const BASE = {
	v: 1,
	mode: "auto",
	selected_model: "claude-sonnet-4-6",
	selected_tier: "Standard",
	classification: { complexity: "moderate", task_type: "general", source: "llm" },
	floor: { tier: "Standard", reasons: ["attachment_document"] },
	ceiling: { tier: "Premium", source: "plan", reasons: [] },
	bound_by: "floor",
	band: null,
	band_disclosed: "capacity_managed",
	shortlist_size: 8,
	pick_reason: "cost_weighted",
	thinking: { requested: false, applied: false },
	credits: { actual: 12, expected: 40 },
	cycles: 1,
	also_ran: [],
	notices: [],
	preference: null,
};

const panel = (over = {}) =>
	mount(RoutingPanel, { props: { receipt: { ...BASE, ...over }, modelName: "Sonnet 4.6" } });

describe("RoutingPanel", () => {
	it("shows three rows on a floor-bound turn", () => {
		expect(panel().findAll(".routing-row")).toHaveLength(3);
	});

	it("shows the allowed row only when the ceiling bound", () => {
		const w = panel({ bound_by: "ceiling", ceiling: { tier: "Standard", source: "plan", reasons: [] } });
		expect(w.findAll(".routing-row")).toHaveLength(4);
		expect(w.text()).toContain("What was allowed");
	});

	it("never names a ceiling that did not bind", () => {
		expect(panel().text()).not.toContain("What was allowed");
	});

	it("renders a notice when one is present", () => {
		const w = panel({ notices: ["downgraded_for_credits"] });
		expect(w.find(".routing-notice").text()).toContain("Capacity was tight");
	});

	it("hides the expected credits, the shortlist size and the also-ran count", () => {
		const text = panel({ also_ran: ["claude-opus-4-6"] }).text();
		expect(text).not.toContain("40");
		expect(text).not.toContain("8");
		expect(text).not.toMatch(/\+\s*1 more/);
	});

	it("shows no credits figure — the footer chip owns the turn's cost", () => {
		// The receipt is per stream cycle, so its figure is a fraction of a
		// turn that paused for approval or delegated. Rendered beneath the chip
		// showing the real total, it read as a contradiction.
		expect(panel().text()).not.toMatch(/credits/i);
	});

	it("is a labelled region with a close control", () => {
		const w = panel();
		expect(w.find("[role='region']").exists()).toBe(true);
		expect(w.find(".routing-close").exists()).toBe(true);
	});

	it("emits close on the button and on Escape", async () => {
		const w = panel();
		await w.find(".routing-close").trigger("click");
		await w.find("[role='region']").trigger("keydown", { key: "Escape" });
		expect(w.emitted("close")).toHaveLength(2);
	});

	it("renders nothing without a receipt", () => {
		const w = mount(RoutingPanel, { props: { receipt: null } });
		expect(w.findAll(".routing-row")).toHaveLength(0);
	});
});
