import { describe, it, expect } from "vitest";
import { buildSetupChecklist } from "./setupChecklist";

const agent = (model_id = "") => ({ id: "a", type: "agent", data: { config: { model_id } } });
const byKey = (items) => Object.fromEntries(items.map((i) => [i.key, i]));

describe("buildSetupChecklist", () => {
	it("flags a fresh chat-built draft", () => {
		const items = byKey(
			buildSetupChecklist({
				workflow: { default_user_id: "", default_model_id: "" },
				schedule: { cron: "", enabled: false },
				triggers: [],
				nodes: [agent()],
				unapproved: [{ tool: "create_document", nodes: ["Draft"] }],
			})
		);
		expect(items.start.state).toBe("todo");
		expect(items.runs_as.state).toBe("todo");
		expect(items.writes.state).toBe("todo");
		expect(items.writes.detail).toContain("create_document");
		expect(items.writes.detail).toContain("won't run unattended");
		expect(items.model.state).toBe("todo");
	});

	it("is all ok for a scheduled agent with a user, model and approved writes", () => {
		const items = buildSetupChecklist({
			workflow: { default_user_id: "ops@example.com", default_model_id: "m1" },
			schedule: { cron: "0 9 * * 1", enabled: true, timezone: "Asia/Kolkata" },
			triggers: [],
			nodes: [agent()],
			unapproved: [],
		});
		expect(items.every((i) => i.state === "ok")).toBe(true);
	});

	it("counts an enabled trigger as a start and an unchecked write list as unknown", () => {
		const items = byKey(
			buildSetupChecklist({
				workflow: { default_user_id: "x" },
				schedule: { cron: "", enabled: false },
				triggers: [
					{ enabled: 1, reference_doctype: "HD Ticket", doctype_event: "after_insert" },
					{ enabled: 1, reference_doctype: "Sales Order", doctype_event: "on_submit" },
				],
				nodes: [],
				unapproved: null,
			})
		);
		expect(items.start.state).toBe("ok");
		expect(items.writes.state).toBe("unknown");
		expect(items.model.state).toBe("ok");
	});

	it("does not call writes ok when the check failed", () => {
		const items = byKey(
			buildSetupChecklist({
				workflow: { default_user_id: "x" },
				schedule: {},
				nodes: [],
				unapproved: null,
				checkError: "down",
			})
		);
		expect(items.writes.state).toBe("unknown");
		expect(items.writes.detail).toBe("Couldn't check: down");
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

	describe("how it starts", () => {
		const start = (schedule, triggers) =>
			byKey(buildSetupChecklist({ workflow: {}, schedule, triggers, nodes: [], unapproved: [] })).start;
		const trigger = (enabled, doctype = "Sales Order", event = "on_submit") => ({
			enabled,
			reference_doctype: doctype,
			doctype_event: event,
		});

		it("says to turn on a schedule that is set but off", () => {
			const item = start({ cron: "0 9 * * 1", enabled: false, timezone: "Asia/Kolkata" }, []);
			expect(item.state).toBe("todo");
			expect(item.detail).toBe("Turn on the schedule: 0 9 * * 1 (Asia/Kolkata)");
			expect(item.actions.map((a) => a.key)).toEqual(["schedule"]);
		});

		it("says to turn on a trigger that exists but is off", () => {
			const item = start({}, [trigger(0, "HD Ticket", "after_insert")]);
			expect(item.state).toBe("todo");
			expect(item.detail).toBe("Turn on the trigger: HD Ticket \u2192 when created");
			expect(item.actions.map((a) => a.key)).toEqual(["triggers"]);
		});

		it("names an enabled trigger", () => {
			const item = start({}, [trigger(1)]);
			expect(item.state).toBe("ok");
			expect(item.detail).toBe("Trigger: Sales Order \u2192 when submitted");
		});

		it("names an enabled schedule", () => {
			const item = start({ cron: "0 9 * * 1", enabled: true, timezone: "UTC" }, [trigger(0)]);
			expect(item.state).toBe("ok");
			expect(item.detail).toBe("Schedule: 0 9 * * 1 (UTC)");
		});

		it("counts extra enabled triggers", () => {
			expect(start({}, [trigger(1), trigger(1, "HD Ticket", "after_insert")]).detail).toBe(
				"Trigger: Sales Order \u2192 when submitted (+1 more)"
			);
		});

		it("asks for a schedule or a trigger when there is neither", () => {
			const item = start({ cron: "", enabled: false }, []);
			expect(item.state).toBe("todo");
			expect(item.detail).toBe("Add a schedule or a trigger");
			expect(item.actions.map((a) => a.key)).toEqual(["schedule", "triggers"]);
		});
	});
});
