import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import BuildPlanCard from "./BuildPlanCard.vue";
import { PLAN_ID, planBlock } from "./buildPlan.testdata";

const buttonsOf = (wrapper) => wrapper.findAll(".plan-actions button");

describe("BuildPlanCard", () => {
	it("shows the summary", () => {
		const wrapper = mount(BuildPlanCard, { props: { block: planBlock() } });
		expect(wrapper.find(".plan-summary").text()).toBe(
			"Track customer regions and show them on a Sales workspace.",
		);
	});

	it("lists the changes that go live first, under a Goes live marker", () => {
		// AR sent the dormant change first; the card still leads with the live one.
		const wrapper = mount(BuildPlanCard, { props: { block: planBlock() } });
		const groups = wrapper.findAll(".plan-group");
		expect(groups.map((g) => g.find(".plan-group-label").text())).toEqual(["Goes live", "Stays dormant"]);
		expect(groups[0].classes()).toContain("plan-group-live");
		expect(groups[0].find(".change-doctype").text()).toBe("Workspace");
		expect(groups[1].find(".change-doctype").text()).toBe("Custom Field");
	});

	it("shows each change's action, record and sentence", () => {
		const wrapper = mount(BuildPlanCard, { props: { block: planBlock() } });
		const [live, dormant] = wrapper.findAll(".plan-change");
		expect(live.find(".change-action").text()).toBe("Create");
		expect(live.find(".change-record").text()).toBe("Sales Regions");
		expect(live.find(".change-description").text()).toBe("Adds a Sales Regions workspace to the sidebar.");
		// A record not yet named reads out its identity.
		expect(dormant.find(".change-record").text()).toBe("Customer · region");
	});

	it("approves with the plan's id", async () => {
		const block = planBlock();
		const wrapper = mount(BuildPlanCard, { props: { block } });
		await buttonsOf(wrapper)[0].trigger("click");
		expect(wrapper.emitted("approve")).toEqual([
			[block.id, [{ interruptId: "int-plan", response: { decision: "approve", plan_id: PLAN_ID } }]],
		]);
	});

	it("asks for changes without answering the card", async () => {
		const wrapper = mount(BuildPlanCard, { props: { block: planBlock() } });
		await buttonsOf(wrapper)[1].trigger("click");
		expect(wrapper.emitted("ask-for-changes")).toHaveLength(1);
		expect(wrapper.emitted("approve")).toBeUndefined();
	});

	it("takes no more clicks once decided", () => {
		// recordInteractionDecision sets `decision` on the click, before the resume is sent.
		const block = { ...planBlock(), decision: { resolution: "approved" } };
		const wrapper = mount(BuildPlanCard, { props: { block } });
		expect(buttonsOf(wrapper).map((b) => b.attributes("disabled"))).toEqual(["", ""]);
	});

	it("shows the mockup only when the plan has one", () => {
		expect(mount(BuildPlanCard, { props: { block: planBlock() } }).find("iframe").exists()).toBe(false);
		const withMockup = mount(BuildPlanCard, {
			props: { block: planBlock({ mockup_html: "<div class='mk-page'>Hi</div>" }) },
		});
		expect(withMockup.find("iframe").attributes("srcdoc")).toContain("<div class='mk-page'>Hi</div>");
	});
});
