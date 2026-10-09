import { __ } from "@/utils/i18n";

const MODEL_NODES = new Set(["agent", "loop"]);

const describeWrites = (unapproved) =>
	unapproved.map((u) => (u.nodes?.length ? `${u.tool} (${u.nodes.join(", ")})` : u.tool)).join("; ");

/** The four things an agent needs before it runs on its own. */
export function buildSetupChecklist({
	workflow,
	schedule,
	enabledTriggerCount = 0,
	nodes = [],
	unapproved,
}) {
	const scheduled = !!(schedule?.enabled && schedule?.cron);
	let startDetail = __("Manual only — add a schedule or an event trigger to run it on its own");
	if (scheduled) startDetail = __("Schedule {0} ({1})", [schedule.cron, schedule.timezone || "UTC"]);
	else if (enabledTriggerCount === 1) startDetail = __("1 event trigger");
	else if (enabledTriggerCount > 1) startDetail = __("{0} event triggers", [enabledTriggerCount]);

	const writeState = unapproved == null ? "unknown" : unapproved.length ? "todo" : "ok";
	const writeDetail = {
		unknown: () => __("Not checked yet"),
		ok: () => __("Every write tool is set to Always allow for the runtime user"),
		todo: () => __("These won't run unattended: {0}", [describeWrites(unapproved)]),
	}[writeState]();

	const modelNodes = nodes.filter((n) => MODEL_NODES.has(n.type));
	const modelOk =
		!modelNodes.length ||
		!!workflow?.default_model_id ||
		modelNodes.every((n) => n.data?.config?.model_id);

	return [
		{
			key: "start",
			state: scheduled || enabledTriggerCount > 0 ? "ok" : "todo",
			label: __("Starts on its own"),
			detail: startDetail,
			actions: [
				{ key: "schedule", label: __("Schedule") },
				{ key: "triggers", label: __("Triggers") },
			],
		},
		{
			key: "runs_as",
			state: workflow?.default_user_id ? "ok" : "todo",
			label: __("Runs as a user"),
			detail: workflow?.default_user_id || __("Not set — agent nodes get no tools"),
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
