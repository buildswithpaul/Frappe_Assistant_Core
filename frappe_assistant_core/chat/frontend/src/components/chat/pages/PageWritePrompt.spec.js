import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PageWritePrompt from "./PageWritePrompt.vue";

const request = (extra = {}) => ({
	message: "This page wants to save ToDo TD-1. The record will hold exactly these fields.",
	note: "",
	fields: [
		{ name: "status", value: "Closed", before: "Open", status: "changed" },
		{ name: "priority", value: "", before: "High", status: "blanked" },
		{ name: "roles", value: "", beforeRows: 2, status: "emptied" },
		{ name: "items", value: "", rows: [[{ name: "item_code", value: "X-1" }, { name: "qty", value: "2" }]] },
		{ name: "description", value: "y".repeat(300) },
	],
	trustable: false,
	hiddenChars: false,
	...extra,
});

let wrapper;
beforeEach(() => vi.useFakeTimers());
afterEach(() => {
	wrapper?.unmount();
	vi.useRealTimers();
});

const allow = () => wrapper.find("[data-test=page-write-allow]");

describe("PageWritePrompt", () => {
	it("keeps Allow off for a moment after it appears, so a click aimed at the page can't land on it", async () => {
		wrapper = mount(PageWritePrompt, { props: { request: request() } });
		expect(allow().attributes("disabled")).toBeDefined();
		await allow().trigger("click");
		expect(wrapper.emitted("decide")).toBeUndefined();
		vi.advanceTimersByTime(600);
		await wrapper.vm.$nextTick();
		expect(allow().attributes("disabled")).toBeDefined();
		vi.advanceTimersByTime(100);
		await wrapper.vm.$nextTick();
		expect(allow().attributes("disabled")).toBeUndefined();
		await allow().trigger("click");
		expect(wrapper.emitted("decide")).toEqual([["once"]]);
	});

	it("turns Allow off again when the request changes", async () => {
		wrapper = mount(PageWritePrompt, { props: { request: request() } });
		vi.advanceTimersByTime(700);
		await wrapper.setProps({ request: request({ message: "This page wants to delete ToDo TD-2." }) });
		expect(allow().attributes("disabled")).toBeDefined();
	});

	it("shows every field: before and after, what is cleared or emptied, child rows, and long values on request", async () => {
		wrapper = mount(PageWritePrompt, { props: { request: request() } });
		const text = wrapper.find(".pwp-fields").text();
		expect(text).toContain("Open");
		expect(text).toContain("Closed");
		expect(text).toContain("will be cleared");
		expect(text).toContain("all 2 rows will be removed");
		expect(text).toContain("item_code X-1");
		expect(text).not.toContain("y".repeat(300));
		await wrapper.find(".pwt-toggle").trigger("click");
		expect(wrapper.find(".pwp-fields").text()).toContain("y".repeat(300));
	});

	it("counts the prompts waiting, says when hidden characters were left out, and explains page trust", () => {
		wrapper = mount(PageWritePrompt, {
			props: {
				request: request({ hiddenChars: true, trustable: true, note: "Allow for this page lets this version of the page run sales_feed again without asking." }),
				total: 3,
			},
		});
		expect(wrapper.find("[data-test=page-write-count]").text()).toBe("1 of 3");
		expect(wrapper.find("[data-test=page-write-hidden]").exists()).toBe(true);
		expect(wrapper.text()).toContain("lets this version of the page run sales_feed again");
		expect(wrapper.find("[data-test=page-write-trust]").exists()).toBe(true);
	});
});
