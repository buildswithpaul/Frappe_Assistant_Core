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
