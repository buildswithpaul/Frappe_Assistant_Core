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

	it("NeedsYou hides on load failure with nothing to show", () => {
		expect(make({ failed: true, items: [] }).find("section").exists()).toBe(false);
	});

	it("failed endpoint still shows the client-side workflow card", () => {
		const wf = { ...base, id: "failed_workflows", href: "/agents", dismissible: true };
		const w = make({ failed: true, items: [wf] });
		expect(w.find("section").exists()).toBe(true);
		expect(w.text()).toContain("overdue invoices");
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

	it("shows the short action as the link text, falling back to the ask", () => {
		expect(make({ items: [{ ...base, action: "Draft reminders" }] }).find(".ny-ask").text()).toBe("Draft reminders →");
		expect(make().find(".ny-ask").text()).toBe("Show overdue →");
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
