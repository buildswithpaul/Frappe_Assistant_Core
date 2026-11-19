import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import WorkflowToolbarActions from "./WorkflowToolbarActions.vue";

function runButton(props) {
	const wrapper = mount(WorkflowToolbarActions, { props: { isAdmin: true, ...props } });
	return wrapper
		.findAll("button")
		.find((b) => b.text().includes("Run") && !b.text().includes("Runs"));
}

describe("Run button", () => {
	it("is disabled on an invalid graph and says why", () => {
		const btn = runButton({
			canRun: false,
			runBlockReason: 'Task "a" is missing a system prompt',
		});
		expect(btn.attributes("disabled")).toBeDefined();
		expect(btn.attributes("title")).toBe('Task "a" is missing a system prompt');
	});

	it("is enabled on a valid graph", () => {
		expect(runButton({ canRun: true }).attributes("disabled")).toBeUndefined();
	});
});

describe("Setup button", () => {
	const labels = (props) =>
		mount(WorkflowToolbarActions, { props: { isAdmin: true, ...props } })
			.findAll("button")
			.map((b) => b.text());

	it("replaces the Schedule, Triggers and Settings buttons", () => {
		const text = labels({ setupProgress: { done: 3, total: 3 } });
		expect(text).not.toContain("Schedule");
		expect(text).not.toContain("Triggers");
		expect(text).not.toContain("Settings");
	});

	it("shows progress while items are left and emits setup", async () => {
		const wrapper = mount(WorkflowToolbarActions, {
			props: { isAdmin: true, setupProgress: { done: 1, total: 3 } },
		});
		const btn = wrapper.findAll("button").find((b) => b.text() === "Setup 1/3");
		await btn.trigger("click");
		expect(wrapper.emitted("setup")).toHaveLength(1);
	});

	it("says Ready once everything is done", () => {
		expect(labels({ setupProgress: { done: 3, total: 3 } })).toContain("Ready");
	});
});

describe("Activate while setup is unfinished", () => {
	const activate = (props) =>
		mount(WorkflowToolbarActions, { props: { isAdmin: true, status: "Draft", ...props } })
			.findAll("button")
			.find((b) => b.text() === "Activate");

	it("is not the primary action and says what is missing", () => {
		const btn = activate({ activateBlockReason: "Choose who it runs as" });
		expect(btn.classes()).not.toContain("primary");
		expect(btn.attributes("title")).toBe("Choose who it runs as");
	});

	it("still emits, so a click opens setup instead of doing nothing", async () => {
		const wrapper = mount(WorkflowToolbarActions, {
			props: { isAdmin: true, status: "Draft", activateBlockReason: "Choose when it runs" },
		});
		await wrapper.findAll("button").find((b) => b.text() === "Activate").trigger("click");
		expect(wrapper.emitted("toggle-status")).toHaveLength(1);
	});

	it("is primary once setup allows it", () => {
		expect(activate({ activateBlockReason: "" }).classes()).toContain("primary");
	});

	it("never blocks Pause", () => {
		const wrapper = mount(WorkflowToolbarActions, {
			props: { isAdmin: true, status: "Active", activateBlockReason: "Choose when it runs" },
		});
		const btn = wrapper.findAll("button").find((b) => b.text() === "Pause");
		expect(btn.classes()).toContain("warning");
	});
});

describe("status toggle while the approval check runs", () => {
	it("is disabled and says it is checking", () => {
		const wrapper = mount(WorkflowToolbarActions, {
			props: { isAdmin: true, status: "Draft", statusBusy: true },
		});
		const btn = wrapper.findAll("button").find((b) => b.text().includes("Checking"));
		expect(btn.attributes("disabled")).toBeDefined();
	});
});
