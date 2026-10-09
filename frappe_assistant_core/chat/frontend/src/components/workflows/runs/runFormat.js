import { __ } from "@/utils/i18n";
import { parseJsonMaybe } from "@/utils/json";

export { parseJsonMaybe };

export function statusClass(status) {
	switch ((status || "").toLowerCase()) {
		case "completed":
			return "badge-success";
		case "running":
			return "badge-running";
		case "queued":
		case "pending":
		case "skipped":
			return "badge-queued";
		case "failed":
			return "badge-danger";
		case "cancelled":
			return "badge-warning";
		case "timed out":
			return "badge-timeout";
		default:
			return "";
	}
}

const TRIGGER_LABELS = {
	manual: () => __("Manual"),
	scheduled: () => __("Scheduled"),
	api: () => __("API"),
	doc_event: () => __("Event"),
};

export function triggerLabel(type) {
	return TRIGGER_LABELS[type]?.() || type || "";
}

export function relativeTime(dateStr) {
	if (!dateStr) return "";
	const mins = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000);
	if (mins < 1) return __("Just now");
	if (mins < 60) return __("{0}m ago", [mins]);
	const hrs = Math.floor(mins / 60);
	if (hrs < 24) return __("{0}h ago", [hrs]);
	return __("{0}d ago", [Math.floor(hrs / 24)]);
}

export function formatDuration(ms) {
	if (!ms) return "";
	if (ms < 1000) return `${ms}ms`;
	if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
	return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

export function formatCredits(credits) {
	if (!credits) return "";
	if (credits < 0.01) return credits.toFixed(4);
	if (credits < 1) return credits.toFixed(2);
	return credits.toFixed(1);
}

export function truncate(text, len) {
	if (!text) return "";
	return text.length > len ? `${text.slice(0, len)}…` : text;
}

export function parseSkippedActions(run) {
	const list = parseJsonMaybe(run?.skipped_actions_detail, []);
	return Array.isArray(list) ? list.filter((x) => x && typeof x === "object") : [];
}

export function skippedCount(run) {
	const n = Number(run?.skipped_actions);
	if (Number.isFinite(n) && n > 0) return Math.floor(n);
	return parseSkippedActions(run).length;
}

/** A run that skipped writes is still Completed; say so in amber instead of hiding it. */
export function runBadge(run) {
	const status = run?.status || "";
	const skipped = status === "Completed" ? skippedCount(run) : 0;
	if (skipped) {
		return {
			text:
				skipped === 1
					? __("Completed · 1 action skipped")
					: __("Completed · {0} actions skipped", [skipped]),
			cls: "badge-warning",
		};
	}
	return { text: status, cls: statusClass(status) };
}

export const OUTPUT_DISPLAY_LIMIT = 10000;

/** What a run that did not finish still produced: its last finished step. */
export function partialOutput(run) {
	if (!run || run.status === "Completed" || run.output_data) return null;
	const done = (run.node_runs || []).filter((n) => n.status === "Completed" && n.output_text);
	const last = done[done.length - 1];
	if (!last) return null;
	const text = last.output_text.slice(0, OUTPUT_DISPLAY_LIMIT);
	return {
		label: last.node_label || last.node_id,
		text,
		truncated: Boolean(last.output_text_truncated) || text.length < last.output_text.length,
	};
}

export function loopSummary(outputText) {
	const out = parseJsonMaybe(outputText, null);
	if (!out || typeof out !== "object" || !("processed" in out)) return null;
	return {
		processed: Number(out.processed) || 0,
		failed: Number(out.failed) || 0,
		skipped: Number(out.skipped_over_limit) || 0,
	};
}
