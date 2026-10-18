import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
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

	describe("Don't show this", () => {
		afterEach(() => vi.useRealTimers());
		const mountAttached = (props = {}) =>
			mount(NeedsYou, {
				attachTo: document.body,
				props: { items: [base], loaded: true, failed: false, variant: "cards", ...props },
			});

		it("each card has an icon-only options button labelled with its title", () => {
			const w = make({ items: [base, { ...base, id: "b", title: "late orders" }] });
			const labels = w.findAll(".ny-options").map((b) => b.attributes("aria-label"));
			expect(labels).toEqual(["More options for overdue invoices", "More options for late orders"]);
			expect(w.find(".ny-options").attributes("aria-expanded")).toBe("false");
		});

		it("opens a one-item menu, and Esc closes it", async () => {
			const w = mountAttached();
			await w.find(".ny-options").trigger("click");
			expect(w.find(".ny-options").attributes("aria-expanded")).toBe("true");
			const items = w.findAll("[role=menuitem]");
			expect(items.map((i) => i.text())).toEqual(["Don't show this on my home"]);
			await w.find(".ny-item").trigger("keydown", { key: "Escape" });
			expect(w.find("[role=menu]").exists()).toBe(false);
		});

		it("choosing it emits hide with the id and shows a quiet note in place", async () => {
			const w = make({ items: [base, { ...base, id: "b" }] });
			await w.find(".ny-options").trigger("click");
			await w.find("[role=menuitem]").trigger("click");
			expect(w.emitted("hide")).toEqual([["a"]]);
			// The parent removes the card; the note takes its slot.
			await w.setProps({ items: [{ ...base, id: "b" }] });
			const rows = w.findAll(".ny-items > li");
			expect(rows[0].classes()).toContain("ny-note");
			expect(rows[0].text()).toContain("Hidden. Bring it back in Settings → Home page.");
			await rows[0].find("button").trigger("click");
			expect(w.emitted("open-settings")).toHaveLength(1);
		});

		it("the note dismisses itself after about six seconds", async () => {
			vi.useFakeTimers();
			const w = make();
			await w.find(".ny-options").trigger("click");
			await w.find("[role=menuitem]").trigger("click");
			await w.setProps({ items: [] });
			expect(w.find(".ny-note").exists()).toBe(true);
			vi.advanceTimersByTime(6100);
			await nextTick();
			expect(w.find(".ny-note").exists()).toBe(false);
		});

		it("the note goes away when the card returns because the hide failed", async () => {
			const w = make();
			await w.find(".ny-options").trigger("click");
			await w.find("[role=menuitem]").trigger("click");
			await w.setProps({ items: [] });
			expect(w.find(".ny-note").exists()).toBe(true);
			await w.setProps({ items: [base] });
			expect(w.find(".ny-note").exists()).toBe(false);
			expect(w.find(".ny-main").exists()).toBe(true);
		});

		it("focus moves into the menu on open and back to the trigger on Esc", async () => {
			const w = mountAttached();
			await w.find(".ny-options").trigger("click");
			await nextTick();
			expect(document.activeElement).toBe(w.find("[role=menuitem]").element);
			await w.find(".ny-item").trigger("keydown", { key: "Escape" });
			expect(document.activeElement).toBe(w.find(".ny-options").element);
			w.unmount();
		});

		it("the menu closes when focus leaves it", async () => {
			const w = mountAttached();
			await w.find(".ny-options").trigger("click");
			await nextTick();
			await w.find(".ny-item").trigger("focusout", { relatedTarget: document.body });
			expect(w.find("[role=menu]").exists()).toBe(false);
			w.unmount();
		});

		it("focus lands on the note's link after hiding", async () => {
			const w = mountAttached();
			await w.find(".ny-options").trigger("click");
			await w.find("[role=menuitem]").trigger("click");
			await w.setProps({ items: [] });
			await nextTick();
			expect(document.activeElement).toBe(w.find(".ny-note-link").element);
			w.unmount();
		});

		it("re-hiding the same card keeps one note and one live timer", async () => {
			vi.useFakeTimers();
			const w = make();
			const hideOnce = async () => {
				await w.find(".ny-options").trigger("click");
				await w.find("[role=menuitem]").trigger("click");
				await w.setProps({ items: [] });
			};
			await hideOnce();
			await w.setProps({ items: [base] }); // the hide failed and the card came back
			vi.advanceTimersByTime(3000);
			await hideOnce();
			expect(w.findAll(".ny-note")).toHaveLength(1);
			// The first note's clock (at 6 s) must not cut the second note short.
			vi.advanceTimersByTime(3500);
			await nextTick();
			expect(w.findAll(".ny-note")).toHaveLength(1);
			vi.advanceTimersByTime(2600);
			await nextTick();
			expect(w.find(".ny-note").exists()).toBe(false);
		});

		it("clears its timers on unmount", async () => {
			vi.useFakeTimers();
			const w = make();
			await w.find(".ny-options").trigger("click");
			await w.find("[role=menuitem]").trigger("click");
			w.unmount();
			expect(vi.getTimerCount()).toBe(0);
		});

		it("says so when the hide failed", () => {
			const w = make({ hideFailed: true });
			expect(w.find("[role=alert]").text()).toBe("Couldn't hide that card. Try again.");
			expect(make().find("[role=alert]").exists()).toBe(false);
		});
	});
});
