import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import ContextRail from "../ContextRail.vue";
import { deriveArtifacts } from "@/utils/contextArtifacts";

// The blocks a stopped turn persists: Stop closed the stream before AR closed
// the helper rows, so they keep the last statuses AR streamed.
const STOPPED_BLOCKS = [
	{
		type: "plan",
		status: "running",
		tasks: [
			{ id: "a", title: "Customer A", status: "running", helper: true },
			{ id: "b", title: "Customer B", status: "pending" },
		],
	},
];

describe("ContextRail on a stopped turn", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("hands the stopped state to the task list", () => {
		const wrapper = mount(ContextRail, {
			props: { artifacts: deriveArtifacts(STOPPED_BLOCKS), live: false, stopped: true },
		});

		expect(wrapper.findAll(".task-row.is-stopped")).toHaveLength(2);
		expect(wrapper.find(".task-summary").text()).toBe("Stopped after 0 of 2 steps");
	});
});

describe("ContextRail on a finished turn", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("hands the finished state to the activity timeline", () => {
		// A tool whose result never arrived is persisted `running` with no end time.
		const blocks = [
			{ type: "tool_call", id: "t1", tool_name: "list_documents", status: "running", startTime: "2026-07-20T09:00:00.000Z" },
		];
		const wrapper = mount(ContextRail, {
			props: { artifacts: deriveArtifacts(blocks), live: false },
		});

		expect(wrapper.find(".tl-row.is-running").exists()).toBe(false);
		expect(wrapper.find(".tl-row .tl-duration").text()).toBe("stopped");
	});
});

describe("ContextRail on a turn paused at a card", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("does not present the paused turn's tool as stopped", () => {
		// AR emits tool_call_start for the model's tool use before the approval
		// hook interrupts it, so a paused turn holds the gated tool as `running`
		// next to its pending card, and the message is not streaming.
		const blocks = [
			{ type: "tool_call", id: "tu-1", tool_name: "create_document", status: "running", startTime: "2026-07-20T09:00:00.000Z" },
			{ type: "interaction", id: "tu-1", status: "pending", tool_name: "create_document" },
		];
		const wrapper = mount(ContextRail, {
			props: { artifacts: deriveArtifacts(blocks), live: false, paused: true },
		});

		expect(wrapper.find(".tl-row.is-running").exists()).toBe(true);
		expect(wrapper.find(".tl-row.is-stopped").exists()).toBe(false);
	});
});
