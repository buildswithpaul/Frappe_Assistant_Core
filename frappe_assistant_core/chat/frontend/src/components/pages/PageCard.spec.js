import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import PageCard from "./PageCard.vue";

const personal = {
	name: "costs-a1b2c3",
	title: "Costs",
	visibility: "Only me",
	draft: false,
	roles: [],
	modified: "2026-10-01 10:00:00",
};
const shared = { ...personal, name: "sales-d4e5f6", title: "Sales", visibility: "Shared", roles: ["Sales Manager", "Accounts User"] };
const draft = { ...shared, draft: true };

const mountCard = (page) => mount(PageCard, { props: { page } });
const heights = (w) => w.findAll(".page-card-bar").map((b) => b.attributes("style"));

describe("PageCard", () => {
	it("shows a personal page's title, who sees it and when it was updated", () => {
		const w = mountCard(personal);
		expect(w.find(".page-card-title").text()).toBe("Costs");
		expect(w.find(".page-card-context").text()).toBe("Only you");
		expect(w.find(".page-card-updated").text()).toMatch(/^Updated /);
		expect(w.find(".page-card-chip").exists()).toBe(false);
	});

	it("writes a fresh update as 'Updated just now'", () => {
		const w = mountCard({ ...personal, modified: new Date().toISOString() });
		expect(w.find(".page-card-updated").text()).toBe("Updated just now");
	});

	it("falls back to the name when untitled", () => {
		expect(mountCard({ ...personal, title: "" }).find(".page-card-title").text()).toBe("costs-a1b2c3");
	});

	it("names the roles a shared page is shared with, on its own line", () => {
		const w = mountCard(shared);
		expect(w.find(".page-card-context").text()).toBe("Shared with Sales Manager, Accounts User");
		expect(w.find(".page-card-updated").text()).toMatch(/^Updated /);
	});

	it("shows the first two roles and +N for the rest", () => {
		const w = mountCard({ ...shared, roles: ["A", "B", "C", "D"] });
		expect(w.find(".page-card-context").text()).toBe("Shared with A, B +2");
	});

	it("says just Shared when a shared page lists no roles", () => {
		expect(mountCard({ ...shared, roles: [] }).find(".page-card-context").text()).toBe("Shared");
	});

	it("shows a Draft chip and who can see it, with the update time below", () => {
		const w = mountCard(draft);
		expect(w.find(".page-card-chip").text()).toBe("Draft");
		expect(w.find(".page-card-context").text()).toBe("Not published yet · only admins see it");
		expect(w.find(".page-card-updated").text()).toMatch(/^Updated /);
	});

	it("tints the preview by kind", () => {
		expect(mountCard(personal).classes()).toContain("page-card--personal");
		expect(mountCard(shared).classes()).toContain("page-card--shared");
		expect(mountCard(draft).classes()).toContain("page-card--draft");
	});

	it("draws a hidden, deterministic preview from the name", () => {
		const a = mountCard(personal);
		expect(a.find(".page-card-preview").attributes("aria-hidden")).toBe("true");
		expect(a.find(".page-card-preview").text()).toBe("");
		expect(a.findAll(".page-card-bar")).toHaveLength(5);
		expect(heights(mountCard(personal))).toEqual(heights(a));
		expect(heights(mountCard({ ...personal, name: "other-zzzz" }))).not.toEqual(heights(a));
	});

	it("is one button that emits open with the name", async () => {
		const w = mountCard(shared);
		expect(w.element.tagName).toBe("BUTTON");
		await w.trigger("click");
		expect(w.emitted("open")).toEqual([["sales-d4e5f6"]]);
	});
});
