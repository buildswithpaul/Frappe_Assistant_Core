import { computed, ref } from "vue";
import { api } from "@/api/client";
import { __ } from "@/utils/i18n";
import { MESSAGE_TOOLS, isMessageTool } from "@/utils/messageTools";

/**
 * Approval-card state for a message tool: the server preview (who it really goes to, which
 * account sends it, whether the user may send) merged with the draft from the tool input.
 * `entry` is null for any other tool, and nothing is fetched.
 */
export function useMessagePreview(getBlock) {
	const entry = computed(() => (isMessageTool(getBlock().tool_name) ? MESSAGE_TOOLS[getBlock().tool_name] : null));
	const preview = ref(null);
	const loading = ref(false);
	const failed = ref(false);

	const fields = computed(() => {
		if (!entry.value) return null;
		const draft = entry.value.read(getBlock().input || {});
		return {
			// What the tool call names wins; the server fills only what it leaves out.
			to: draft.to?.length ? draft.to : preview.value?.to || [],
			cc: draft.cc,
			subject: draft.subject || preview.value?.subject || "",
			body: draft.body,
		};
	});

	const blockedReason = computed(() => {
		if (preview.value?.can_send === false) return preview.value.reason || "";
		// Approving an email with no recipient would only fail after the click.
		if (preview.value && fields.value && !fields.value.to.length) return __("This email has no recipient.");
		return null;
	});

	async function load() {
		if (!entry.value) return;
		loading.value = true;
		try {
			preview.value = await api.tools.messagePreview(
				getBlock().tool_name,
				entry.value.previewArgs(getBlock().input || {}),
			);
		} catch {
			failed.value = true;
		} finally {
			loading.value = false;
		}
	}

	load();

	return { entry, preview, loading, failed, fields, blockedReason };
}
