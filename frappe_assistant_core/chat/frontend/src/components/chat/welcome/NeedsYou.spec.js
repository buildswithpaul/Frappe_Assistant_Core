import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import NeedsYou from "./NeedsYou.vue";

const base = { id: "a", tone: "danger", source: "Sales", count: 3, title: "overdue invoices", detail: "d", ask: "Show overdue" };
const make = (props = {}) =>
	mount(NeedsYou, { props: { items: [base], loaded: true, failed: false, variant: "cards", ...props } });

describe("NeedsYou", () => {
	it("NeedsYou hides while loading", () => {
		expect(make({ loaded: false }).find("section").exists()).toBe(false);
	});

	it("NeedsYou hides on load failure", () => {
		expect(make({ failed: true }).find("section").exists()).toBe(false);
	});

	it("shows caught-up line when empty", () => {
		expect(make({ items: [] }).text()).toContain("Nothing is waiting on you right now.");
	});

	it("click emits ask with the item prompt", async () => {
		const w = make();
		await w.find(".ny-main").trigger("click");
		expect(w.emitted("ask")).toEqual([["Show overdue"]]);
		expect(w.emitted("navigate")).toBeUndefined();
	});

	it("href item emits navigate", async () => {
		const w = make({ items: [{ ...base, id: "failed_workflows", href: "/agents" }] });
		await w.find(".ny-main").trigger("click");
		expect(w.emitted("navigate")).toEqual([["/agents"]]);
		expect(w.emitted("ask")).toBeUndefined();
	});

	it("only dismissible items show dismiss", async () => {
		const w = make({ items: [base, { ...base, id: "b", dismissible: true }] });
		const buttons = w.findAll(".ny-dismiss");
		expect(buttons).toHaveLength(1);
		expect(buttons[0].attributes("aria-label")).toBeTruthy();
		await buttons[0].trigger("click");
		expect(w.emitted("dismiss")).toEqual([["b"]]);
	});
});
