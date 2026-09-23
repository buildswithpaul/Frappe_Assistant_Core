import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import RoutingSettings from "../RoutingSettings.vue";

const list = vi.fn();
const setStatus = vi.fn();
const setMode = vi.fn();
const remove = vi.fn();

vi.mock("@/api/client", () => ({
	api: {
		routingPreferences: {
			list: (...a) => list(...a),
			setStatus: (...a) => setStatus(...a),
			setMode: (...a) => setMode(...a),
			remove: (...a) => remove(...a),
			create: vi.fn(),
			forecast: vi.fn(),
		},
	},
}));

vi.mock("@/composables/useToast", () => ({
	useToast: () => ({ showError: vi.fn(), showSuccess: vi.fn() }),
}));

const RULE = {
	preference_id: "P1",
	scope: "Tenant",
	match_kind: "keyword",
	match_value: "invoice",
	target_tier: "Economy",
	direction: "prefer_cheaper",
	status: "active",
	match_count: 3,
	created_by_user_id: "owner@example.com",
	rule_mode: "shadow",
};

function payload(over = {}) {
	return { mine: [], team: [RULE], mode: "shadow", can_manage_team: false, ...over };
}

async function render(over = {}) {
	list.mockResolvedValue(payload(over));
	const w = mount(RoutingSettings);
	await flushPromises();
	return w;
}

describe("RoutingSettings", () => {
	beforeEach(() => {
		list.mockReset();
		setStatus.mockReset();
		setMode.mockReset();
		remove.mockReset();
	});

	it("marks a rule still in its trial as Learning", async () => {
		// Sec 4.7 brake 1: a rule that visibly does nothing teaches its
		// earliest adopters that the setting is a lie. It now says so per
		// rule, because that is the thing an admin can act on.
		const w = await render();
		expect(w.text()).toContain("Learning");
		expect(w.text()).toContain("not changing which model answers");
	});

	it("marks a live rule as Live and stops apologising for it", async () => {
		const w = await render({ team: [{ ...RULE, rule_mode: "on" }] });
		expect(w.text()).toContain("Live");
		expect(w.text()).not.toContain("not changing which model answers");
	});

	it("treats an absent rule_mode as learning, never as live", async () => {
		// A column added to an existing table arrives empty, and the whole
		// feature is built to prevent a rule that silently starts applying.
		const { rule_mode, ...noMode } = RULE;
		const w = await render({ team: [noMode] });
		expect(w.text()).toContain("Learning");
	});

	it("only warns about the kill switch, not about the global mode", async () => {
		// shadow and on both mean "not off" now; a banner for either would be
		// telling an admin their live rule is not live.
		const on = await render({ mode: "on" });
		expect(on.text()).not.toContain("switched off");
		const shadow = await render({ mode: "shadow" });
		expect(shadow.text()).not.toContain("switched off");
		const off = await render({ mode: "off" });
		expect(off.text()).toContain("switched off");
	});

	it("lets an admin take their own rule live without anyone else", async () => {
		setMode.mockResolvedValue({ preference_id: "P1", rule_mode: "on" });
		const w = await render({ can_manage_team: true });
		const go = w.findAll("button").find((b) => b.text() === "Go live");
		expect(go).toBeTruthy();
		await go.trigger("click");
		await flushPromises();
		expect(setMode).toHaveBeenCalledWith("P1", "on");
	});

	it("lets an admin send a live rule back to its trial", async () => {
		setMode.mockResolvedValue({ preference_id: "P1", rule_mode: "shadow" });
		const w = await render({
			team: [{ ...RULE, rule_mode: "on" }],
			can_manage_team: true,
		});
		const back = w.findAll("button").find((b) => b.text() === "Back to learning");
		await back.trigger("click");
		await flushPromises();
		expect(setMode).toHaveBeenCalledWith("P1", "shadow");
	});

	it("offers a plain member no way to change a rule", async () => {
		const w = await render({ can_manage_team: false });
		const labels = w.findAll("button").map((b) => b.text());
		expect(labels).not.toContain("Go live");
		expect(labels).not.toContain("Back to learning");
	});

	it("shows a member the workspace rules governing them", async () => {
		const w = await render();
		expect(w.text()).toContain("use Economy");
	});

	it("reads sensibly when the rule text is withheld", async () => {
		// A member who did not author a team rule gets match_value: null.
		const w = await render({
			team: [{ ...RULE, match_value: null }],
		});
		expect(w.text()).toContain("a rule set by your workspace matches");
		expect(w.text()).toContain("use Economy");
	});

	it("gives a member no controls at all", async () => {
		const w = await render({ can_manage_team: false });
		expect(w.find(".rule-controls").exists()).toBe(false);
		expect(w.findComponent({ name: "RoutingRuleForm" }).exists()).toBe(false);
	});

	it("gives an admin the controls and the form", async () => {
		const w = await render({ can_manage_team: true });
		expect(w.find(".rule-controls").exists()).toBe(true);
		expect(w.findComponent({ name: "RoutingRuleForm" }).exists()).toBe(true);
	});

	it("suspends a rule and reloads", async () => {
		const w = await render({ can_manage_team: true });
		setStatus.mockResolvedValue({});
		// Selected by label, not position: the controls row gained a mode
		// button, and a positional selector silently tests the wrong one.
		await w
			.findAll(".rule-controls .rule-link")
			.find((b) => b.text() === "Suspend")
			.trigger("click");
		await flushPromises();
		expect(setStatus).toHaveBeenCalledWith("P1", "suspended");
		expect(list).toHaveBeenCalledTimes(2);
	});

	it("offers to re-enable a suspended rule rather than hiding it", async () => {
		const w = await render({
			can_manage_team: true,
			team: [{ ...RULE, status: "suspended" }],
		});
		const labels = w.findAll(".rule-controls .rule-link").map((b) => b.text());
		expect(labels).toContain("Enable");
		expect(w.text()).toContain("suspended");
	});

	it("says when a rule has never matched instead of showing a bare zero", async () => {
		const w = await render({ team: [{ ...RULE, match_count: 0 }] });
		expect(w.text()).toContain("Not matched yet");
	});

	it("does not call a failed load an empty list", async () => {
		// "No rules yet" after a 500 tells an admin their policy is gone.
		list.mockRejectedValue(new Error("boom"));
		const w = mount(RoutingSettings);
		await flushPromises();
		expect(w.text()).not.toContain("No rules yet");
		expect(w.text()).toContain("Couldn't load");
	});

	it("offers a retry when the load failed", async () => {
		list.mockRejectedValue(new Error("boom"));
		const w = mount(RoutingSettings);
		await flushPromises();
		list.mockResolvedValue(payload());
		await w.find(".routing-retry").trigger("click");
		await flushPromises();
		expect(w.text()).toContain("use Economy");
	});

	it("shows an empty state rather than nothing", async () => {
		const w = await render({ team: [] });
		expect(w.text()).toContain("No rules yet");
	});
});

describe("removed rules", () => {
	const GONE = {
		...RULE,
		preference_id: "P9",
		status: "removed",
		match_value: "acquisition",
		modified: "2026-09-07 21:53:34.219976",
	};

	beforeEach(() => {
		list.mockReset();
		setStatus.mockReset();
		setMode.mockReset();
		remove.mockReset();
	});

	it("says nothing at all when there are none", async () => {
		const w = await render({ removed: [] });
		expect(w.find(".routing-removed").exists()).toBe(false);
	});

	it("answers the question an admin actually arrives with", async () => {
		// "Why does an old reply say a rule chose its model when I deleted
		// that rule?" — the receipt is a snapshot, so it names a rule that is
		// gone. This section is where that gets explained.
		const w = await render({ removed: [GONE] });
		expect(w.text()).toContain("don't affect any new reply");
		expect(w.text()).toContain("older messages naming a rule still make sense");
	});

	it("reads in the past tense", async () => {
		const w = await render({ removed: [GONE] });
		const line = w.find(".rule-item-removed .rule-sentence").text();
		expect(line).toContain("this used Economy");
		expect(line).not.toContain("use Economy");
	});

	it("says when it went, without tripping over Frappe's non-ISO datetime", async () => {
		const w = await render({ removed: [GONE] });
		const meta = w.find(".rule-item-removed .rule-meta").text();
		expect(meta).toContain("Workspace rule");
		expect(meta).toMatch(/removed .*2026/);
		expect(meta).not.toContain("Invalid Date");
	});

	it("survives a row with no modified stamp", async () => {
		const w = await render({ removed: [{ ...GONE, modified: undefined }] });
		expect(w.find(".rule-item-removed .rule-meta").text()).toBe("Workspace rule");
	});

	it("offers no controls — removal is terminal", async () => {
		const w = await render({ removed: [GONE], can_manage_team: true });
		expect(w.find(".rule-item-removed .rule-controls").exists()).toBe(false);
	});

	it("keeps removed rules out of the live workspace list", async () => {
		const w = await render({ team: [], removed: [GONE] });
		expect(w.text()).toContain("No rules yet");
	});
});

describe("defaults set by FAC Cloud", () => {
	const PLATFORM = {
		preference_id: "A1",
		scope: "Application",
		match_kind: "keyword",
		match_value: "invoice",
		target_tier: "Economy",
		status: "active",
		rule_mode: "on",
		read_only: true,
		created_by_user_id: "operator@example.com",
	};

	beforeEach(() => {
		list.mockReset();
		setStatus.mockReset();
		setMode.mockReset();
		remove.mockReset();
	});

	it("says nothing when there are none", async () => {
		const w = await render({ platform: [] });
		expect(w.text()).not.toContain("Set by FAC Cloud");
	});

	it("shows them, so an admin can explain their own routing", async () => {
		const w = await render({ platform: [PLATFORM] });
		expect(w.text()).toContain("Set by FAC Cloud");
		expect(w.find(".rule-item-platform .rule-sentence").text()).toBe(
			"When a message mentions “invoice”, use Economy."
		);
	});

	it("states the two things that bound them", async () => {
		// Both are true and both are load-bearing for trust: a workspace rule
		// wins over a default, and no rule of any scope can outrun the plan.
		const w = await render({ platform: [PLATFORM] });
		expect(w.text()).toContain("Your own rules above take priority");
		expect(w.text()).toContain("above what your plan allows");
	});

	it("offers no controls, not even to an admin", async () => {
		const w = await render({ platform: [PLATFORM], can_manage_team: true });
		expect(w.find(".rule-item-platform .rule-controls").exists()).toBe(false);
	});

	it("keeps them out of the workspace list", async () => {
		const w = await render({ team: [], platform: [PLATFORM] });
		expect(w.text()).toContain("No rules yet");
	});
});
