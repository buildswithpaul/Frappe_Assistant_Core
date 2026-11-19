import { api } from "@/api/client";
import { proposedTimezone } from "@/components/workflows/builder/scheduleWords";

/**
 * What Activate switches on: the configured schedule (in the proposed zone)
 * and, for a draft, every trigger that was created switched off. A resume
 * leaves triggers as the person left them. Triggers go first: saving an
 * enabled schedule flips a Draft to Active on AR, so it is the last write.
 */
export function useActivationStarts({
	workflowStore,
	workflowId,
	scheduleConfig,
	triggers,
	browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone,
}) {
	async function enableStarts({ fromDraft }) {
		if (fromDraft) {
			for (const trigger of triggers.value.filter((t) => Number(t.enabled) !== 1)) {
				await api.workflows.triggers.toggle(trigger.name, true);
				trigger.enabled = 1;
			}
		}

		const schedule = scheduleConfig.value;
		if (schedule.cron && !schedule.enabled) {
			const timezone = proposedTimezone(schedule, browserZone);
			await workflowStore.setSchedule(
				workflowId.value,
				schedule.cron,
				timezone,
				true,
				schedule.defaultInput?.trim() || null
			);
			scheduleConfig.value = { ...schedule, timezone, enabled: true };
		}
	}

	return { enableStarts };
}
