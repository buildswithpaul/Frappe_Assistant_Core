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
			workflowStore: {
				loadWorkflow: vi.fn().mockResolvedValue(result),
				loadModels: vi.fn().mockResolvedValue(),
			},
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
			workflowStore: {
				loadWorkflow: vi.fn().mockRejectedValue(new Error("nope")),
				loadModels: vi.fn().mockResolvedValue(),
			},
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

	it("loads models alongside the workflow", async () => {
		const { loadCurrentWorkflow, deps } = setup(PAUSED_KOLKATA);
		await loadCurrentWorkflow();
		expect(deps.workflowStore.loadModels).toHaveBeenCalledTimes(1);
	});

	it("lays out a graph whose nodes are stacked on one spot", async () => {
		const stacked = {
			...PAUSED_KOLKATA,
			graph_json: JSON.stringify({
				nodes: [
					{ id: "a", type: "agent", config: {} },
					{ id: "b", type: "agent", config: {} },
				],
				edges: [{ source: "a", target: "b" }],
			}),
		};
		const { loadCurrentWorkflow, deps, wasRelaidOut } = setup(stacked);
		await loadCurrentWorkflow();
		expect(wasRelaidOut.value).toBe(true);
		const [a, b] = deps.nodes.value;
		expect(a.position).not.toEqual(b.position);
	});

	it("keeps an author's spaced layout as it is", async () => {
		const spaced = {
			...PAUSED_KOLKATA,
			graph_json: JSON.stringify({
				nodes: [
					{ id: "a", type: "agent", position: { x: 10, y: 10 }, config: {} },
					{ id: "b", type: "agent", position: { x: 200, y: 10 }, config: {} },
				],
				edges: [],
			}),
		};
		const { loadCurrentWorkflow, deps, wasRelaidOut } = setup(spaced);
		await loadCurrentWorkflow();
		expect(wasRelaidOut.value).toBe(false);
		expect(deps.nodes.value[1].position).toEqual({ x: 200, y: 10 });
	});
});
