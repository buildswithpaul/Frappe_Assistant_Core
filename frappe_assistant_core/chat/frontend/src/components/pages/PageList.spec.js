import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it } from "vitest";

import PageList from "./PageList.vue";

const pages = [
	{ name: "costs-a1b2c3", title: "Costs", visibility: "Only me", draft: false, modified: "2026-10-01 10:00:00" },
	{ name: "sales-d4e5f6", title: "Sales", visibility: "Shared", draft: true, modified: "2026-10-02 10:00:00" },
];

async function mountList(props) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/chat", component: { template: "<div />" } }],
	});
	return mount(PageList, { global: { plugins: [router] }, props });
}

describe("PageList", () => {
	it("shows who can see each page, a Draft chip and when it was updated", async () => {
		const w = await mountList({ pages });
		const rows = w.findAll(".page-list-row");
		expect(rows[0].findAll(".page-list-chip").map((c) => c.text())).toEqual(["Only you"]);
		expect(rows[1].findAll(".page-list-chip").map((c) => c.text())).toEqual(["Shared", "Draft"]);
		expect(rows[0].text()).toContain("Updated");
		expect(rows[0].text()).toContain("Costs");
	});

	it("says there are no pages and links back to chat", async () => {
		const w = await mountList({ pages: [] });
		expect(w.text()).toContain("No pages yet");
		expect(w.find("a").attributes("href")).toBe("/chat");
	});

	it("emits open with the page name", async () => {
		const w = await mountList({ pages });
		await w.findAll(".page-list-row")[1].trigger("click");
		expect(w.emitted("open")).toEqual([["sales-d4e5f6"]]);
	});
});
