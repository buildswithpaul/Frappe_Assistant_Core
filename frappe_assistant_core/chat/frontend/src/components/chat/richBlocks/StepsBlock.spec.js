import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import StepsBlock from "./StepsBlock.vue";
import { parseSteps } from "./stepsBody";

const mountSteps = (props) => mount(StepsBlock, { props });
const titles = (wrapper) => wrapper.findAll(".step-title").map((el) => el.text());
const states = (wrapper) =>
	wrapper.findAll(".step-item").map((el) =>
		el.classes("step-done") ? "done" : el.classes("step-active") ? "active" : "pending"
	);

describe("StepsBlock", () => {
	// Seen on a demo site (#35329): the model wrote the fence as JSON, as it does for callouts and
	// metrics, and the block showed one step whose text was the JSON.
	it("reads a JSON list of steps with their statuses", () => {
		const body = JSON.stringify([
			{ title: "Purchase Order", status: "complete" },
			{ title: "Purchase Receipt", status: "current", description: "Ready to submit" },
			{ title: "Purchase Invoice", status: "pending" },
		]);
		const wrapper = mountSteps({ body });

		expect(titles(wrapper)).toEqual(["Purchase Order", "Purchase Receipt", "Purchase Invoice"]);
		expect(states(wrapper)).toEqual(["done", "active", "pending"]);
		expect(wrapper.find(".step-body").text()).toBe("Ready to submit");
		expect(wrapper.text()).not.toContain('"status"');
	});

	it("reads the documented form: a heading per step with its text under it", () => {
		const body = [
			"## Step 1: Create Draft",
			'Create the Sales Invoice from the Sales Order using the "Make" button.',
			"",
			"## Step 2: Verify Line Items",
			"Check that quantities and rates match the Delivery Note.",
		].join("\n");
		const wrapper = mountSteps({ body, current: 2 });

		expect(titles(wrapper)).toEqual(["Create Draft", "Verify Line Items"]);
		expect(wrapper.findAll(".step-body").map((el) => el.text())).toEqual([
			'Create the Sales Invoice from the Sales Order using the "Make" button.',
			"Check that quantities and rates match the Delivery Note.",
		]);
		expect(states(wrapper)).toEqual(["done", "active"]);
		expect(wrapper.html()).not.toContain("##");
	});

	it("keeps one step per line and strips numbers and bullets", () => {
		const wrapper = mountSteps({ body: "1. Quote\n\n2. Order\n- Invoice" });

		expect(titles(wrapper)).toEqual(["Quote", "Order", "Invoice"]);
	});

	it("still renders inline markdown inside a step", () => {
		const wrapper = mountSteps({ body: "Ship **before** you `bill`" });

		expect(wrapper.find(".step-title").html()).toContain("<strong>before</strong>");
		expect(wrapper.find(".step-title").html()).toContain("<code>bill</code>");
	});

	it("takes the title from the fence, or from a JSON object holding the steps", () => {
		expect(mountSteps({ body: "a\nb", title: "Buying" }).find(".steps-title").text()).toBe("Buying");
		const body = JSON.stringify({ title: "Selling", steps: ["Quote", { name: "Order", status: "done" }] });
		const wrapper = mountSteps({ body });

		expect(wrapper.find(".steps-title").text()).toBe("Selling");
		expect(titles(wrapper)).toEqual(["Quote", "Order"]);
		expect(states(wrapper)).toEqual(["pending", "done"]);
	});

	it("treats text that only looks like JSON as lines", () => {
		expect(parseSteps("[not json\nsecond").steps.map((s) => s.title)).toEqual(["[not json", "second"]);
	});

	it("never renders a script from a step", () => {
		const body = JSON.stringify([{ title: "<img src=x onerror=alert(1)>", description: "<script>x()</script>" }]);

		expect(mountSteps({ body }).html()).not.toMatch(/onerror|<script/);
	});
});
