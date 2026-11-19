import { __ } from "@/utils/i18n";
import { describeSchedule } from "./scheduleWords";

const MODEL_NODES = new Set(["agent", "loop"]);

const describeWrites = (unapproved) =>
	unapproved.map((u) => (u.nodes?.length ? `${u.tool} (${u.nodes.join(", ")})` : u.tool)).join("; ");

const eventLabel = (event) =>
	({
		after_insert: __("when created"),
		on_update: __("when updated"),
		on_submit: __("when submitted"),
		on_cancel: __("when cancelled"),
		on_trash: __("when deleted"),
	})[event] || event;

export const describeTrigger = (t) => `${t.reference_doctype} → ${eventLabel(t.doctype_event)}`;

/**
 * How the agent starts. Configured is enough: schedules and triggers stay off
 * until Activate turns them on, so "off" is not something left to do.
 */
function describeStart(schedule, triggers) {
	if (schedule?.cron) return { state: "ok", detail: describeSchedule(schedule.cron, schedule.timezone) };
	if (triggers.length) {
		const more = triggers.length > 1 ? __(" (+{0} more)", [triggers.length - 1]) : "";
		return { state: "ok", detail: describeTrigger(triggers[0]) + more };
	}
	return { state: "todo", detail: __("Pick a schedule or a document event") };
}

/** What an agent needs before it runs on its own; `required` items gate Activate. */
export function buildSetupChecklist({
	workflow,
	schedule,
	triggers = [],
	nodes = [],
	unapproved,
	checkError = null,
}) {
	const start = describeStart(schedule, triggers);

	const writeState = unapproved == null ? "unknown" : unapproved.length ? "todo" : "ok";
	const writeDetail = {
		unknown: () => (checkError ? __("Couldn't check: {0}", [checkError]) : __("Not checked yet")),
		ok: () => __("Every write tool may run unattended"),
		todo: () => __("These won't run unattended: {0}", [describeWrites(unapproved)]),
	}[writeState]();

	const agentNodes = nodes.filter((n) => MODEL_NODES.has(n.type));
	const hasRuntimeUser =
		!!workflow?.default_user_id ||
		(agentNodes.length > 0 && agentNodes.every((n) => n.data?.config?.user_id));

	return [
		{
			key: "runs_as",
			required: true,
			state: hasRuntimeUser ? "ok" : "todo",
			label: __("Runs as"),
			blockReason: __("Choose who it runs as"),
			detail:
				workflow?.default_user_id ||
				(hasRuntimeUser ? __("Set on each task") : __("Not set — agent steps get no tools")),
		},
		{
			key: "start",
			required: true,
			state: start.state,
			label: __("When it runs"),
			blockReason: __("Choose when it runs"),
			detail: start.detail,
		},
		{
			key: "writes",
			required: false,
			state: writeState,
			label: __("Write tools"),
			detail: writeDetail,
		},
		{
			key: "model",
			required: false,
			state: "ok",
			label: __("Model"),
			detail: workflow?.default_model_id || __("Workspace default"),
		},
	];
}

/** Why Activate is blocked, or "" when every required item is done. */
export function activationBlockReason(items) {
	return items.find((i) => i.required && i.state !== "ok")?.blockReason || "";
}

/** Progress over the items a person acts on; the model is never left to do. */
export function setupProgress(items) {
	const counted = items.filter((i) => i.key !== "model");
	return { done: counted.filter((i) => i.state === "ok").length, total: counted.length };
}

/**
 * The `enabled` to save a schedule with. AR's set_schedule flips a Draft agent
 * to Active when a schedule is saved enabled, so only Activate may switch one
 * on; editing a live (or paused-but-enabled) schedule keeps it as it was.
 */
export function scheduleEnabledOnSave({ wasEnabled, status }) {
	return status === "Active" || (!!wasEnabled && status !== "Draft");
}
