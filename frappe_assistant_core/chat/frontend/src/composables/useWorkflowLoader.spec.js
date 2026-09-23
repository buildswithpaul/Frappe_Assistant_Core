import { describe, it, expect, vi } from "vitest";
import { ref } from "vue";
import { scheduleFromWorkflow, useWorkflowLoader } from "@/composables/useWorkflowLoader";

/**
 * The exact payload AR's workflows.get_workflow returns for a paused
 * Asia/Kolkata schedule. `timezone`, not `schedule_timezone`; Check fields
 * are ints.
 */
const PAUSED_KOLKATA = {
	name: "WF-00007",
	workflow_name: "Nightly digest",
	graph_json: '{"version":"1.0","nodes":[],"edges":[]}',
	schedule_enabled: 0,
	cron_expression: "0 9 * * *",
	timezone: "Asia/Kolkata",
	default_input: "",
};

describe("scheduleFromWorkflow", () => {
	it("reads the timezone AR actually sends", () => {
		expect(scheduleFromWorkflow(PAUSED_KOLKATA).timezone).toBe("Asia/Kolkata");
	});

	it("keeps a paused schedule paused", () => {
		expect(scheduleFromWorkflow(PAUSED_KOLKATA).enabled).toBe(false);
	});

	it("treats the Check int 1 as enabled", () => {
		expect(scheduleFromWorkflow({ ...PAUSED_KOLKATA, schedule_enabled: 1 }).enabled).toBe(true);
	});

	it("falls back to UTC only when no timezone was stored", () => {
		expect(scheduleFromWorkflow({}).timezone).toBe("UTC");
	});

	it("round-trips the cron expression and default input", () => {
		const schedule = scheduleFromWorkflow({
			...PAUSED_KOLKATA,
			default_input: "{\"scope\":\"all\"}",
		});
		expect(schedule.cron).toBe("0 9 * * *");
		expect(schedule.defaultInput).toBe('{"scope":"all"}');
	});
});

describe("useWorkflowLoader", () => {
	function setup(result) {
		const scheduleConfig = ref({ cron: "x", timezone: "UTC", defaultInput: "", enabled: true });
		const deps = {
			workflowStore: { loadWorkflow: vi.fn().mockResolvedValue(result) },
			workflowId: ref("WF-00007"),
			nodes: ref([]),
			edges: ref([]),
			globalSettings: ref({}),
			hasSaved: ref(false),
			scheduleConfig,
		};
		return { ...useWorkflowLoader(deps), scheduleConfig, deps };
	}

	it("hydrates a paused Kolkata schedule without flipping it to live UTC", async () => {
		const { loadCurrentWorkflow, scheduleConfig } = setup(PAUSED_KOLKATA);
		await loadCurrentWorkflow();
		expect(scheduleConfig.value.timezone).toBe("Asia/Kolkata");
		expect(scheduleConfig.value.enabled).toBe(false);
	});

	it("clears stale schedule state when the workflow has none", async () => {
		const { loadCurrentWorkflow, scheduleConfig } = setup({
			name: "WF-1",
			graph_json: null,
		});
		await loadCurrentWorkflow();
		expect(scheduleConfig.value.cron).toBe("");
		expect(scheduleConfig.value.enabled).toBe(false);
	});

	it("surfaces a load failure", async () => {
		const scheduleConfig = ref({});
		const { loadCurrentWorkflow, loadError } = useWorkflowLoader({
			workflowStore: { loadWorkflow: vi.fn().mockRejectedValue(new Error("nope")) },
			workflowId: ref("WF-1"),
			nodes: ref([]),
			edges: ref([]),
			globalSettings: ref({}),
			hasSaved: ref(false),
			scheduleConfig,
		});
		await loadCurrentWorkflow();
		expect(loadError.value).toBe("nope");
	});
});
