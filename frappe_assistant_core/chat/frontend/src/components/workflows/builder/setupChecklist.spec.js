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
				enabledTriggerCount: 0,
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
			enabledTriggerCount: 0,
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
				enabledTriggerCount: 2,
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
});
