import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import RoutingRuleForm from "../routing/RoutingRuleForm.vue";

const create = vi.fn();
const forecast = vi.fn();

vi.mock("@/api/client", () => ({
	api: { routingPreferences: { create: (...a) => create(...a), forecast: (...a) => forecast(...a) } },
}));

async function filled(value = "invoice", tier = "Economy") {
	const w = mount(RoutingRuleForm);
	await w.find('input[type="text"]').setValue(value);
	const selects = w.findAll("select");
	await selects[1].setValue(tier);
	return w;
}

describe("RoutingRuleForm", () => {
	beforeEach(() => {
		create.mockReset();
		forecast.mockReset();
		forecast.mockResolvedValue({ cost_multiplier: 1, requires_confirmation: false,
									 rates_reviewed: true, direction: "prefer_cheaper" });
		create.mockResolvedValue({ preference_id: "P1" });
	});

	it("will not submit an empty rule", async () => {
		const w = mount(RoutingRuleForm);
		expect(w.find(".rule-save").attributes("disabled")).toBeDefined();
	});

	it("saves a cheapness rule without stopping to confirm", async () => {
		const w = await filled();
		await w.find("form").trigger("submit");
		await flushPromises();
		expect(create).toHaveBeenCalledWith("keyword", "invoice", "Economy");
		expect(w.emitted("created")).toBeTruthy();
	});

	it("stops for a second confirmation on a material increase", async () => {
		// Sec 4.7 brake 8. Nothing is saved on the first press.
		forecast.mockResolvedValue({ cost_multiplier: 5, requires_confirmation: true,
									 rates_reviewed: true, direction: "prefer_stronger" });
		const w = await filled("reconcile", "Premium");
		await w.find("form").trigger("submit");
		await flushPromises();
		expect(create).not.toHaveBeenCalled();
		expect(w.find(".rule-save").text()).toBe("Yes, add it");
		expect(w.text()).toContain("5× what they do now");
	});

	it("saves on the second press", async () => {
		forecast.mockResolvedValue({ cost_multiplier: 5, requires_confirmation: true,
									 rates_reviewed: true, direction: "prefer_stronger" });
		const w = await filled("reconcile", "Premium");
		await w.find("form").trigger("submit");
		await flushPromises();
		await w.find("form").trigger("submit");
		await flushPromises();
		expect(create).toHaveBeenCalledWith("keyword", "reconcile", "Premium");
	});

	it("says when the rates behind the forecast were never reviewed", async () => {
		forecast.mockResolvedValue({ cost_multiplier: 5, requires_confirmation: true,
									 rates_reviewed: false, direction: "prefer_stronger" });
		const w = await filled("reconcile", "Premium");
		await w.find("form").trigger("submit");
		await flushPromises();
		expect(w.text()).toContain("nobody has reviewed");
	});

	it("warns that extra keywords narrow rather than widen", async () => {
		const w = await filled("invoice overdue");
		expect(w.text()).toContain("Every word must appear");
	});

	it("labels a task-type rule as a task type, not as words", async () => {
		const w = mount(RoutingRuleForm);
		await w.findAll("select")[0].setValue("task_type");
		expect(w.text()).toContain("this task type");
		expect(w.text()).not.toContain("these words");
	});

	it("will not let you submit the value the server refuses", async () => {
		const w = mount(RoutingRuleForm);
		await w.findAll("select")[0].setValue("task_type");
		await w.find('input[type="text"]').setValue("general");
		expect(w.find(".rule-save").attributes("disabled")).toBeDefined();
	});

	it("warns about the value the server will refuse", async () => {
		const w = mount(RoutingRuleForm);
		await w.findAll("select")[0].setValue("task_type");
		await w.find('input[type="text"]').setValue("general");
		expect(w.text()).toContain("pick something narrower");
	});

	it("re-asks for confirmation when the rule is edited after the warning", async () => {
		forecast.mockResolvedValue({ cost_multiplier: 5, requires_confirmation: true,
									 rates_reviewed: true, direction: "prefer_stronger" });
		const w = await filled("reconcile", "Premium");
		await w.find("form").trigger("submit");
		await flushPromises();
		await w.find('input[type="text"]').setValue("something else");
		expect(w.find(".rule-save").text()).toBe("Add rule");
	});

	it("reports a save failure instead of silently clearing", async () => {
		create.mockRejectedValue(new Error("nope"));
		const w = await filled();
		await w.find("form").trigger("submit");
		await flushPromises();
		expect(w.emitted("error")[0][0]).toBe("nope");
		expect(w.find('input[type="text"]').element.value).toBe("invoice");
	});
});
