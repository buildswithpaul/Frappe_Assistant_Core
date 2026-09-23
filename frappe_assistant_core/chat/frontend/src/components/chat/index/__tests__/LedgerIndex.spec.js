import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import LedgerIndex from "../LedgerIndex.vue";

const entries = [
	{ kind: "exchange", key: "ex-0", index: 0, messageId: "m1", heading: "Toolbox Talks — Riverside",
		toolCount: 3, hasChart: false, hasFiles: false, approval: null, time: "09:14",
		streaming: false, completed: true },
	{ kind: "divider", key: "div-2" },
	{ kind: "exchange", key: "ex-3", index: 3, messageId: "m2", heading: "Create HD Tickets",
		toolCount: 1, hasChart: false, hasFiles: false, approval: "resolved", time: "09:48",
		streaming: false, completed: true },
	{ kind: "exchange", key: "ex-5", index: 5, messageId: null, heading: "Audit summary",
		toolCount: 0, hasChart: false, hasFiles: false, approval: null, time: "",
		streaming: true, completed: false },
];

function mountIndex(props = {}) {
	return mount(LedgerIndex, {
		props: { entries, activeIndex: 3, mode: "full", pinned: [], ...props },
	});
}

describe("LedgerIndex", () => {
	it("renders one button per exchange inside a labelled nav", () => {
		const wrapper = mountIndex();
		expect(wrapper.find("nav[aria-label='Conversation index']").exists()).toBe(true);
		expect(wrapper.findAll(".index-entry")).toHaveLength(3);
		expect(wrapper.find(".index-divider").exists()).toBe(true);
	});
	it("marks the active entry with aria-current and shows the gold approval dot", () => {
		const wrapper = mountIndex();
		const active = wrapper.find("[aria-current='true']");
		expect(active.text()).toContain("Create HD Tickets");
		expect(active.find(".gold-dot").exists()).toBe(true);
	});
	it("emits jump with the message index on click", async () => {
		const wrapper = mountIndex();
		await wrapper.findAll(".index-entry")[0].trigger("click");
		expect(wrapper.emitted("jump")[0]).toEqual([0]);
	});
	it("streaming entry shows dots instead of meta", () => {
		expect(mountIndex().find(".index-streaming").exists()).toBe(true);
	});
	it("spine mode renders ticks, not headings", () => {
		const wrapper = mountIndex({ mode: "spine" });
		expect(wrapper.findAll(".spine-tick")).toHaveLength(3);
		expect(wrapper.find(".index-heading").exists()).toBe(false);
	});
	it("renders pinned chips and emits unpin", async () => {
		const wrapper = mountIndex({ pinned: [{ messageId: "m1", heading: "RAMS table" }] });
		expect(wrapper.find(".index-pin-chip").text()).toContain("RAMS table");
		await wrapper.find(".index-pin-remove").trigger("click");
		expect(wrapper.emitted("unpin")[0]).toEqual(["m1"]);
	});
});
