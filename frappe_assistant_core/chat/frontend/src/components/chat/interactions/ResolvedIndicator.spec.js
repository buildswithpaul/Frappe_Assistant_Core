import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ResolvedIndicator from "./ResolvedIndicator.vue";
import { planBlock } from "./buildPlan.testdata";

const labelOf = (block) =>
	mount(ResolvedIndicator, { props: { block, interactionType: block.interactionType } })
		.find(".resolved-label")
		.text();

describe("ResolvedIndicator for a build plan", () => {
	// applyInteractionDecisions copies the decision's resolution and response onto the block.
	it("reads Plan approved once the plan is approved", () => {
		const response = { decision: "approve", plan_id: "p" };
		expect(labelOf({ ...planBlock(), status: "approved", userResponse: response })).toBe("Plan approved");
	});

	it("reads Changes requested when the user typed feedback instead", () => {
		expect(labelOf({ ...planBlock(), status: "answered", userResponse: "Use a Select field" })).toBe(
			"Changes requested",
		);
	});
});
