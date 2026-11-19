import { describe, it, expect } from "vitest";
import {
	buildSetupChecklist,
	activationBlockReason,
	setupProgress,
	scheduleEnabledOnSave,
	describeTrigger,
} from "./setupChecklist";

const agent = (model_id = "") => ({ id: "a", type: "agent", data: { config: { model_id } } });
const byKey = (items) => Object.fromEntries(items.map((i) => [i.key, i]));
const trigger = (enabled, doctype = "Sales Order", event = "on_submit") => ({
	enabled,
	reference_doctype: doctype,
	doctype_event: event,
});

describe("buildSetupChecklist", () => {
	it("orders the items runs as, start, writes, model", () => {
		const items = buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [], unapproved: [] });
		expect(items.map((i) => i.key)).toEqual(["runs_as", "start", "writes", "model"]);
	});

	it("requires a runtime user and a start, but not approved writes or a model", () => {
		const items = byKey(buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [], unapproved: [] }));
		expect(items.runs_as.required).toBe(true);
		expect(items.start.required).toBe(true);
		expect(items.writes.required).toBe(false);
		expect(items.model.required).toBe(false);
	});

	it("flags a fresh template import: no user, schedule off, unapproved write", () => {
		const items = byKey(
			buildSetupChecklist({
				workflow: { default_user_id: "", default_model_id: "" },
				schedule: { cron: "", enabled: false },
				triggers: [],
				nodes: [agent()],
				unapproved: [{ tool: "send_email", nodes: ["Send email"] }],
			})
		);
		expect(items.runs_as.state).toBe("todo");
		expect(items.start.state).toBe("todo");
		expect(items.writes.state).toBe("todo");
		expect(items.writes.detail).toContain("send_email");
	});

	it("never counts an unset model as a to-do: the workspace default is valid", () => {
		const items = byKey(
			buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [agent()], unapproved: [] })
		);
		expect(items.model.state).toBe("ok");
		expect(items.model.detail).toBe("Workspace default");
	});

	it("names the default model when one is chosen", () => {
		const items = byKey(
			buildSetupChecklist({ workflow: { default_model_id: "m1" }, schedule: {}, nodes: [], unapproved: [] })
		);
		expect(items.model.detail).toBe("m1");
	});

	it("does not call writes ok when the check failed or has not run", () => {
		const failed = byKey(
			buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [], unapproved: null, checkError: "down" })
		);
		expect(failed.writes.state).toBe("unknown");
		expect(failed.writes.detail).toBe("Couldn't check: down");
		const unchecked = byKey(buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [], unapproved: null }));
		expect(unchecked.writes.state).toBe("unknown");
	});

	it("accepts per-node users in place of a default user", () => {
		const own = (id) => ({ id, type: "agent", data: { config: { user_id: "a@example.com" } } });
		const items = byKey(
			buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [own("1"), own("2")], unapproved: [] })
		);
		expect(items.runs_as.state).toBe("ok");
		const mixed = byKey(
			buildSetupChecklist({ workflow: {}, schedule: {}, nodes: [own("1"), agent()], unapproved: [] })
		);
		expect(mixed.runs_as.state).toBe("todo");
	});

	describe("when it runs", () => {
		const start = (schedule, triggers = []) =>
			byKey(buildSetupChecklist({ workflow: {}, schedule, triggers, nodes: [], unapproved: [] })).start;

		it("is done once a schedule is configured, even while it is off: Activate turns it on", () => {
			const item = start({ cron: "0 9 * * 1", enabled: false, timezone: "Asia/Kolkata" });
			expect(item.state).toBe("ok");
			expect(item.detail).toBe("Every Monday at 09:00 (Asia/Kolkata)");
		});

		it("is done once a trigger exists, even while it is off", () => {
			const item = start({}, [trigger(0, "HD Ticket", "after_insert")]);
			expect(item.state).toBe("ok");
			expect(item.detail).toBe("HD Ticket → when created");
		});

		it("counts extra triggers", () => {
			expect(start({}, [trigger(1), trigger(0, "HD Ticket", "after_insert")]).detail).toBe(
				"Sales Order → when submitted (+1 more)"
			);
		});

		it("names the schedule first when there are both", () => {
			expect(start({ cron: "0 9 * * *", timezone: "UTC" }, [trigger(1)]).detail).toBe(
				"Every day at 09:00 (UTC)"
			);
		});

		it("asks for a schedule or a trigger when there is neither", () => {
			const item = start({ cron: "", enabled: false });
			expect(item.state).toBe("todo");
			expect(item.detail).toBe("Pick a schedule or a document event");
		});
	});
});

describe("activationBlockReason", () => {
	const items = (workflow, schedule, triggers = []) =>
		buildSetupChecklist({ workflow, schedule, triggers, nodes: [], unapproved: [] });

	it("names the first open required item", () => {
		expect(activationBlockReason(items({}, {}))).toBe("Choose who it runs as");
		expect(activationBlockReason(items({ default_user_id: "x" }, {}))).toBe("Choose when it runs");
	});

	it("is empty once the required items are done, whatever the writes say", () => {
		const done = buildSetupChecklist({
			workflow: { default_user_id: "x" },
			schedule: { cron: "0 9 * * 1" },
			nodes: [],
			unapproved: [{ tool: "send_email", nodes: [] }],
		});
		expect(activationBlockReason(done)).toBe("");
	});
});

describe("setupProgress", () => {
	it("counts runs as, start and writes, not the model", () => {
		const items = buildSetupChecklist({
			workflow: { default_user_id: "x" },
			schedule: {},
			nodes: [],
			unapproved: [],
		});
		expect(setupProgress(items)).toEqual({ done: 2, total: 3 });
	});
});

describe("scheduleEnabledOnSave", () => {
	it("never switches a schedule on for a draft: AR would activate the agent", () => {
		expect(scheduleEnabledOnSave({ wasEnabled: false, status: "Draft" })).toBe(false);
	});

	it("keeps a live agent's schedule running when it is edited", () => {
		expect(scheduleEnabledOnSave({ wasEnabled: false, status: "Active" })).toBe(true);
		expect(scheduleEnabledOnSave({ wasEnabled: true, status: "Active" })).toBe(true);
	});

	it("keeps a paused agent's enabled schedule enabled, so Resume brings it back", () => {
		expect(scheduleEnabledOnSave({ wasEnabled: true, status: "Paused" })).toBe(true);
		expect(scheduleEnabledOnSave({ wasEnabled: false, status: "Paused" })).toBe(false);
	});
});

describe("describeTrigger", () => {
	it("words a trigger the way a person would", () => {
		expect(describeTrigger(trigger(1, "HD Ticket", "after_insert"))).toBe("HD Ticket → when created");
	});
});
