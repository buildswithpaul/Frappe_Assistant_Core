import { onBeforeUnmount, onMounted } from "vue";

import { baseCall } from "@/api/_core";
import { chat } from "@/api/domains/chat";
import { onSpaSocketEvent } from "@/composables/useStreaming";
import { usePagePanel } from "@/composables/usePagePanel";
import { createDispatcher } from "@/utils/browserToolDispatch";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import { askConfirm } from "@/widget/panel/confirmQueue";

const loadHtml2canvas = () => import("html2canvas-pro").then((m) => m.default || m);

// The same bounds as the Desk widget's capture (widget/desk/browserTools.js).
const MAX_SCREENSHOT_SCALE = 1.5;
const SCREENSHOT_IMAGE_TIMEOUT_MS = 3000;

/** Why the open page cannot be captured, or null when it can. */
function pageProblem() {
	const view = usePagePanel().pageView.value;
	if (!view?.element) return __("No page is open in the panel.");
	if (view.draft) return __("A draft's preview can't be captured. Publish the page to look at it.");
	return null;
}

/**
 * FACO's screenshot in the chat SPA: the page open beside the chat, never the chat itself, so
 * `selector` and `full_page` do not apply.
 */
export async function takePageScreenshot(params = {}) {
	const problem = pageProblem();
	if (problem) return { error: problem };
	const view = usePagePanel().pageView.value;
	try {
		const html2canvas = await loadHtml2canvas();
		const canvas = await html2canvas(view.element, {
			useCORS: true,
			// allowTaint lets cross-origin pixels in, and toBlob then throws on the tainted canvas.
			allowTaint: false,
			scale: Math.min(window.devicePixelRatio || 1, MAX_SCREENSHOT_SCALE),
			imageTimeout: SCREENSHOT_IMAGE_TIMEOUT_MS,
			logging: false,
		});
		const size = { width: canvas.width, height: canvas.height };
		const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", (params.quality || 80) / 100));
		// A canvas past the browser's maximum size encodes to null.
		if (!blob) return { error: "Screenshot too large to encode.", ...size };

		const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
		const file = new File([blob], `page_screenshot_${timestamp}.jpg`, { type: "image/jpeg" });
		const uploaded = await chat.uploadFile(file);
		return {
			success: true,
			file_url: uploaded.file_url,
			file_name: uploaded.file_name,
			...size,
			mime_type: "image/jpeg",
		};
	} catch (error) {
		logger.error("Page screenshot failed:", error);
		return { error: `Screenshot failed: ${error.message}` };
	}
}

/**
 * Let FACO look at the page open in the side panel. Calls arrive on the SPA socket, which sits in
 * the conversation's task_progress room; each screenshot asks the user first.
 *
 * @param {{getSessionId: () => string|null}} options
 */
export function useSpaBrowserTools({ getSessionId }) {
	// A call without a session went to every tab of the user (an older AR); a Desk widget may hold it.
	const onSessionCall = (event, fn) => onSpaSocketEvent(event, (data) => (data?.session_id ? fn(data) : undefined));
	const dispatcher = createDispatcher({
		transport: { on: onSessionCall, call: baseCall },
		handlers: { take_screenshot: takePageScreenshot },
		confirmTools: new Set(["take_screenshot"]),
		describe: () => __("The page open beside the chat"),
		// With nothing to capture, answer at once rather than ask the user to approve nothing.
		preflight: pageProblem,
		confirm: askConfirm,
		getSessionId,
	});

	onMounted(() => {
		dispatcher.start();
		// Without a conversation the drain would empty the user's shared queue instead.
		if (getSessionId()) dispatcher.drainPending();
	});
	onBeforeUnmount(() => dispatcher.stop());
}
