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
		const text = labels({ setupTodo: 0 });
		expect(text).toContain("Setup");
		expect(text).not.toContain("Schedule");
		expect(text).not.toContain("Triggers");
		expect(text).not.toContain("Settings");
	});

	it("shows how many items are still to do and emits setup", async () => {
		const wrapper = mount(WorkflowToolbarActions, { props: { isAdmin: true, setupTodo: 2 } });
		const btn = wrapper.findAll("button").find((b) => b.text() === "Setup (2)");
		await btn.trigger("click");
		expect(wrapper.emitted("setup")).toHaveLength(1);
	});
});
