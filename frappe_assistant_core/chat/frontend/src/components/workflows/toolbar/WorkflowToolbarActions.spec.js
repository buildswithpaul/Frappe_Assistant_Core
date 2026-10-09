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
