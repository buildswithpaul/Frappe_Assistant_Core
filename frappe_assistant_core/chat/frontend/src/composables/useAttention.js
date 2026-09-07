// Conditional landing attention line (spec §5): failed workflow runs in the
// last 24h. Capability-gated, called after first paint, fail-SILENT — the
// landing never surfaces an error for this nice-to-have.
//
// Two refinements over the naive "any recent failure" count:
//   - Archived-workflow failures are excluded. "Delete" in the SPA is a
//     soft-delete (status → Archived) and archived workflows are hidden from
//     the list, so their failures are not actionable — counting them left a
//     nudge pointing at a workflow the user can no longer see.
//   - Dismissible via a watermark. Dismiss records the newest failure
//     currently shown; the banner only returns when a NEWER failure arrives,
//     so dismissing never blinds the user to future problems.
import { ref } from "vue";
import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";

export const FAILURE_WINDOW_MS = 24 * 60 * 60 * 1000;
const DISMISS_KEY = "faco.attention_dismissed_ts";
// Fetch a small batch of the most-recent failures (not just 1) so an archived
// run near the top doesn't crowd out an actionable one before we filter.
const RUN_FETCH_LIMIT = 20;
// The archived list is paged; 100 (the server cap) covers any realistic tenant.
const ARCHIVED_FETCH_LIMIT = 100;

function runTime(run) {
	const raw = String(run.started_at || run.completed_at || "").replace(" ", "T");
	const ts = new Date(raw).getTime();
	return Number.isNaN(ts) ? null : ts;
}

function dismissedWatermark() {
	const raw = Number(localStorage.getItem(DISMISS_KEY));
	return Number.isFinite(raw) ? raw : 0;
}

export function useAttention() {
	const attention = ref(null);
	const userStore = useUserStore();

	async function loadAttention() {
		if (!userStore.workflowsEnabled) return;
		try {
			const result = await api.workflows.listRuns(null, "Failed", 0, RUN_FETCH_LIMIT);
			const cutoff = Date.now() - FAILURE_WINDOW_MS;
			const watermark = dismissedWatermark();

			const recent = (result?.runs || [])
				.map((run) => ({ run, ts: runTime(run) }))
				.filter(({ ts }) => ts !== null && ts >= cutoff && ts > watermark);
			if (recent.length === 0) return;

			const actionable = await excludeArchived(recent);
			if (actionable.length === 0) return;

			const latestTs = Math.max(...actionable.map(({ ts }) => ts));
			attention.value = {
				count: actionable.length,
				workflowName: actionable.length === 1 ? actionable[0].run.workflow || null : null,
				latestTs,
			};
		} catch {
			/* fail-silent by design */
		}
	}

	// Drop runs whose parent workflow is archived. We match against the
	// ARCHIVED set (not the active set) on purpose: the active list is paged,
	// so testing "is it active?" would misclassify any active workflow beyond
	// the first page as archived and hide a real failure. Matching archived
	// fails OPEN instead — an unresolved workflow is kept (shown), so a lookup
	// gap or a huge archived list never suppresses an actionable failure.
	async function excludeArchived(recent) {
		try {
			const wfResult = await api.workflows.list("Archived", 0, ARCHIVED_FETCH_LIMIT);
			const archived = new Set((wfResult?.workflows || []).map((w) => w.name));
			if (archived.size === 0) return recent;
			return recent.filter(({ run }) => !archived.has(run.workflow));
		} catch {
			return recent;
		}
	}

	function dismiss() {
		try {
			if (attention.value?.latestTs) {
				localStorage.setItem(DISMISS_KEY, String(attention.value.latestTs));
			}
		} catch {
			/* storage unavailable (private mode / quota) — still dismiss this session */
		}
		attention.value = null;
	}

	return { attention, loadAttention, dismiss };
}
