import { __ } from "@/utils/i18n";

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

const describeTrigger = (t) => `${t.reference_doctype} \u2192 ${eventLabel(t.doctype_event)}`;

/** How the agent starts, in the words a person would use, and which controls fix it. */
function describeStart(schedule, triggers) {
	const cron = schedule?.cron;
	const zone = schedule?.timezone || "UTC";
	const onTriggers = triggers.filter((t) => Number(t.enabled) === 1);
	const offTrigger = triggers.find((t) => Number(t.enabled) !== 1);
	const actions = {
		schedule: { key: "schedule", label: __("Schedule") },
		triggers: { key: "triggers", label: __("Triggers") },
	};

	if (cron && schedule.enabled)
		return { state: "ok", detail: __("Schedule: {0} ({1})", [cron, zone]), actions: [actions.schedule] };
	if (onTriggers.length) {
		const more = onTriggers.length > 1 ? __(" (+{0} more)", [onTriggers.length - 1]) : "";
		return {
			state: "ok",
			detail: __("Trigger: {0}", [describeTrigger(onTriggers[0])]) + more,
			actions: [actions.triggers],
		};
	}
	const todo = [];
	if (cron) todo.push({ line: __("Turn on the schedule: {0} ({1})", [cron, zone]), action: actions.schedule });
	if (offTrigger)
		todo.push({ line: __("Turn on the trigger: {0}", [describeTrigger(offTrigger)]), action: actions.triggers });
	if (!todo.length)
		return {
			state: "todo",
			detail: __("Add a schedule or a trigger"),
			actions: [actions.schedule, actions.triggers],
		};
	return { state: "todo", detail: todo.map((t) => t.line).join(". "), actions: todo.map((t) => t.action) };
}

/** The four things an agent needs before it runs on its own. */
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
		ok: () => __("Every write tool is set to Always allow for the runtime user"),
		todo: () => __("These won't run unattended: {0}", [describeWrites(unapproved)]),
	}[writeState]();

	const modelNodes = nodes.filter((n) => MODEL_NODES.has(n.type));
	const modelOk =
		!modelNodes.length ||
		!!workflow?.default_model_id ||
		modelNodes.every((n) => n.data?.config?.model_id);

	const agentNodes = nodes.filter((n) => MODEL_NODES.has(n.type));
	const hasRuntimeUser =
		!!workflow?.default_user_id ||
		(agentNodes.length > 0 && agentNodes.every((n) => n.data?.config?.user_id));

	return [
		{
			key: "start",
			state: start.state,
			label: __("How it starts"),
			detail: start.detail,
			actions: start.actions,
		},
		{
			key: "runs_as",
			state: hasRuntimeUser ? "ok" : "todo",
			label: __("Runs as a user"),
			detail: workflow?.default_user_id || (hasRuntimeUser ? __("Set on each task") : __("Not set — agent nodes get no tools")),
			actions: [{ key: "settings", label: __("Settings") }],
		},
		{
			key: "writes",
			state: writeState,
			label: __("Write tools approved"),
			detail: writeDetail,
			actions: [{ key: "recheck", label: __("Re-check") }],
		},
		{
			key: "model",
			state: modelOk ? "ok" : "todo",
			label: __("Model chosen"),
			detail: modelOk
				? workflow?.default_model_id || __("Each task picks its own model")
				: __("No default model — tasks without one use the provider default"),
			actions: [{ key: "settings", label: __("Settings") }],
		},
	];
}
