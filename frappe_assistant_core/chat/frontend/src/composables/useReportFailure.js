import { useChatStore } from "@/stores/chatStore";
import { useSupportStore } from "@/stores/supportStore";
import { buildReportPrefill } from "@/utils/reportableError";

/** Opens Help & Feedback as an issue, seeded with a failed turn's details. */
export function useReportFailure() {
	const support = useSupportStore();
	const chat = useChatStore();

	return function reportFailure({ code, message, at }) {
		support.open({
			mode: "issue",
			conversationId: chat.currentSessionId || null,
			prefill: buildReportPrefill({ code, message, at }),
		});
	};
}
