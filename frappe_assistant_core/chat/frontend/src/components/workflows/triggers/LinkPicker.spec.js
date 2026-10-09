import { describe, it, expect, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import LinkPicker from "@/components/workflows/triggers/LinkPicker.vue";

const OPTIONS = [
	{ value: "grand_total", label: "Grand Total" },
	{ value: "net_total", label: "Net Total" },
	{ value: "customer", label: "Customer" },
];

describe("LinkPicker", () => {
	let wrapper;
	afterEach(() => wrapper?.unmount());

	async function type(text) {
		wrapper = mount(LinkPicker, { props: { options: OPTIONS }, attachTo: document.body });
		const input = wrapper.find("input");
		await input.trigger("focus");
		await input.setValue(text);
		await nextTick();
	}
	const rows = () => [...document.querySelectorAll(".link-picker-option")].map((e) => e.textContent);

	it("finds a field by its exact fieldname, not only its label", async () => {
		await type("grand_total");

		expect(rows()).toHaveLength(1);
		expect(rows()[0]).toContain("Grand Total");
	});

	it("still finds a field by its label", async () => {
		await type("net");

		expect(rows()).toHaveLength(1);
		expect(rows()[0]).toContain("Net Total");
	});

	it("renders its own strings through the translator", async () => {
		await type("zzz");

		expect(document.querySelector(".link-picker-empty").textContent.trim()).toBe("No matches");
		expect(wrapper.find("input").attributes("placeholder")).toBe("Start typing…");
	});
});
