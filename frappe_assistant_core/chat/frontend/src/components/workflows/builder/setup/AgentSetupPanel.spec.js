import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import AgentSetupPanel from "./AgentSetupPanel.vue";
import {
	buildSetupChecklist,
	activationBlockReason,
	setupProgress,
} from "@/components/workflows/builder/setupChecklist";

const ME = "avery@example.com";

function mountPanel({ workflow = {}, schedule = {}, triggers = [], status = "Draft", warnings = [], stuck = [] } = {}) {
	const fullSchedule = { cron: "", timezone: "UTC", defaultInput: "", enabled: false, ...schedule };
	const items = buildSetupChecklist({ workflow, schedule: fullSchedule, triggers, nodes: [], unapproved: warnings });
	return mount(AgentSetupPanel, {
		props: {
			items,
			progress: setupProgress(items),
			blockReason: activationBlockReason(items),
			status,
			workflow,
			schedule: fullSchedule,
			triggers,
			warnings,
			stuckTools: stuck,
			currentUser: ME,
		},
	});
}

// A marketplace import arrives like this: no runtime user, the template's
// cron saved switched off in UTC, and an unapproved write tool.
const imported = {
	workflow: { default_user_id: "" },
	schedule: { cron: "0 9 * * 1", timezone: "UTC", enabled: false },
	warnings: [{ tool: "send_email", server: "", user: "", nodes: ["Send email"] }],
};

describe("AgentSetupPanel", () => {
	it("blocks Activate on a fresh import and says what to do first", () => {
		const wrapper = mountPanel(imported);
		const activate = wrapper.get("[data-test=setup-activate]");
		expect(activate.attributes("disabled")).toBeDefined();
		expect(wrapper.text()).toContain("Choose who it runs as");
		expect(wrapper.text()).toContain("1 of 3 done");
	});

	it("Run as me saves the signed-in user", async () => {
		const wrapper = mountPanel(imported);
		await wrapper.get("[data-test=run-as-me]").trigger("click");
		expect(wrapper.emitted("save-settings")[0]).toEqual([{ default_user_id: ME }]);
	});

	it("shows the imported schedule in words, without cron", () => {
		const text = mountPanel(imported).text();
		expect(text).toMatch(/Every Monday at 09:00/);
		expect(text).not.toContain("0 9 * * 1");
	});

	it("saves an edited schedule switched off on a draft, so editing never activates it", async () => {
		const wrapper = mountPanel(imported);
		await wrapper.get("[data-test=schedule-change]").trigger("click");
		await wrapper.get("[data-test=schedule-freq]").setValue("daily");
		await wrapper.get("[data-test=schedule-picker]").trigger("submit");
		const [config] = wrapper.emitted("save-schedule")[0];
		expect(config.cron).toBe("0 9 * * *");
		expect(config.enabled).toBe(false);
	});

	it("keeps a live agent's schedule on when it is edited", async () => {
		const wrapper = mountPanel({
			workflow: { default_user_id: ME },
			schedule: { cron: "0 9 * * 1", timezone: "Asia/Kolkata", enabled: true },
			status: "Active",
		});
		await wrapper.get("[data-test=schedule-change]").trigger("click");
		await wrapper.get("[data-test=schedule-picker]").trigger("submit");
		expect(wrapper.emitted("save-schedule")[0][0].enabled).toBe(true);
	});

	it("opens the picker straight away when the agent has no way to start", () => {
		expect(mountPanel().find("[data-test=schedule-picker]").exists()).toBe(true);
	});

	it("offers Allow unattended only for the signed-in user's own tools", () => {
		const wrapper = mountPanel({
			workflow: { default_user_id: ME },
			schedule: { cron: "0 9 * * 1" },
			warnings: [
				{ tool: "send_email", server: "", user: ME, nodes: [] },
				{ tool: "create_document", server: "", user: "ops@example.com", nodes: [] },
			],
		});
		expect(wrapper.findAll("[data-test=allow-tool]")).toHaveLength(1);
		expect(wrapper.get("[data-test=ask-runtime-user]").text()).toContain("ops@example.com");
	});

	it("drops the Allow button for a tool whose saved preference did not clear the warning", () => {
		const wrapper = mountPanel({
			workflow: { default_user_id: ME },
			schedule: { cron: "0 9 * * 1" },
			warnings: [{ tool: "send_email", server: "", user: ME, nodes: [] }],
			stuck: ["send_email"],
		});
		expect(wrapper.find("[data-test=allow-tool]").exists()).toBe(false);
		expect(wrapper.get("[data-test=ask-runtime-user]").exists()).toBe(true);
	});

	it("enables Activate once the required items are done, even with an unapproved write", async () => {
		const wrapper = mountPanel({ ...imported, workflow: { default_user_id: ME } });
		const activate = wrapper.get("[data-test=setup-activate]");
		expect(activate.attributes("disabled")).toBeUndefined();
		await activate.trigger("click");
		expect(wrapper.emitted("activate")).toHaveLength(1);
	});

	it("has no Activate footer on a live agent", () => {
		const wrapper = mountPanel({
			workflow: { default_user_id: ME },
			schedule: { cron: "0 9 * * 1", enabled: true },
			status: "Active",
		});
		expect(wrapper.find("[data-test=setup-activate]").exists()).toBe(false);
	});
});

describe("Run as me", () => {
	it("is not offered to a username AR cannot resolve, like Administrator", () => {
		const items = buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [], unapproved: [] });
		const wrapper = mount(AgentSetupPanel, {
			props: {
				items,
				progress: setupProgress(items),
				schedule: { cron: "", timezone: "UTC", defaultInput: "", enabled: false },
				currentUser: "Administrator",
			},
		});
		expect(wrapper.find("[data-test=run-as-me]").exists()).toBe(false);
		expect(wrapper.find("[data-test=run-as-other]").exists()).toBe(true);
	});
});
