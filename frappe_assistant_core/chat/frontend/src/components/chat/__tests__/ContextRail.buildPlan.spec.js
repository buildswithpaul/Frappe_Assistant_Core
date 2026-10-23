import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import ContextRail from "../ContextRail.vue";
import { planBlock } from "../interactions/buildPlan.testdata";
import { deriveArtifacts } from "@/utils/contextArtifacts";

describe("ContextRail with a build plan waiting", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("names the plan by its summary", () => {
		expect(deriveArtifacts([planBlock()]).approval).toMatchObject({
			kind: "build_plan",
			title: "Track customer regions and show them on a Sales workspace.",
		});
	});

	it("says a plan is waiting and offers to review it", () => {
		const wrapper = mount(ContextRail, { props: { artifacts: deriveArtifacts([planBlock()]), live: false } });
		expect(wrapper.find(".rail-approval-count").text()).toBe("Plan waiting");
		expect(wrapper.find(".rail-approval-btn").text()).toBe("Review plan");
	});
});
