import { onBeforeUnmount, onMounted } from "vue";

import { baseCall } from "@/api/_core";
import { chat } from "@/api/domains/chat";
import { onSpaSocketEvent } from "@/composables/useStreaming";
import { usePagePanel } from "@/composables/usePagePanel";
import { useChatStore } from "@/stores/chatStore";
import { createDispatcher } from "@/utils/browserToolDispatch";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import { askConfirm } from "@/widget/panel/confirmQueue";

const loadHtml2canvas = () => import("html2canvas-pro").then((m) => m.default || m);

// The same bounds as the Desk widget's capture (widget/desk/browserTools.js).
const MAX_SCREENSHOT_SCALE = 1.5;
const SCREENSHOT_IMAGE_TIMEOUT_MS = 3000;
// How long a capture waits for a write to the open page to land and redraw.
const PAGE_SETTLE_TIMEOUT_MS = 10000;
// The client_type the chat app sends with its turns (api/domains/chat.js).
const SPA_CLIENT_TYPE = "spa";

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
 *
 * @param {object} params the tool's parameters
 * @param {string} [askedAbout] the page open when the user was asked; another page is not captured
 */
export async function takePageScreenshot(params = {}, askedAbout = undefined) {
	const panel = usePagePanel();
	const problem = pageProblem();
	if (problem) return { error: problem };
	// A capture right after a change must show the new version: wait for the write to land and
	// the page to redraw, then for the frame to paint.
	if (!(await panel.whenPageSettled(PAGE_SETTLE_TIMEOUT_MS))) {
		return { error: __("The page is still updating. Try again in a moment.") };
	}
	await new Promise((resolve) => requestAnimationFrame(() => resolve()));
	const settledProblem = pageProblem();
	if (settledProblem) return { error: settledProblem };
	if (askedAbout !== undefined && panel.openName.value !== askedAbout) {
		return { error: __("Another page was opened before this one could be captured. Ask again.") };
	}
	const view = panel.pageView.value;
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
		if (!blob) return { error: __("Screenshot too large to encode."), ...size };

		const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
		const file = new File([blob], `page_screenshot_${timestamp}.jpg`, { type: "image/jpeg" });
		const uploaded = await chat.uploadFile(file);
		return {
			success: true,
			file_url: uploaded.file_url,
			file_name: uploaded.file_name,
			...size,
			mime_type: "image/jpeg",
			...(view.codeWaiting && {
				note: __(
					"The page's new code has not run: the user has not clicked Run new version yet, so this picture shows the page without it.",
				),
			}),
		};
	} catch (error) {
		logger.error("Page screenshot failed:", error);
		return { error: __("Screenshot failed: {0}", [error.message]) };
	}
}

const pageCopy = () => ({
	action: __("Look at the page"),
	detail: __(
		"FACO wants to look at the page open beside the chat and send a picture of it to the assistant. It may contain any data the page shows.",
	),
});

/**
 * Let FACO look at the page open in the side panel. Calls arrive on the SPA socket, which sits in
 * the conversation's task_progress room; each screenshot asks the user first, and "Always Allow"
 * covers that page in that conversation only.
 *
 * @param {{getSessionId: () => string|null}} options
 */
export function useSpaBrowserTools({ getSessionId }) {
	// The page each call was about when it was accepted, keyed by the call's params object, which
	// the dispatcher hands unchanged to preflight and then to the handler.
	const askedAbout = new WeakMap();
	function preflight(toolName, params) {
		const problem = pageProblem();
		if (!problem) askedAbout.set(params, usePagePanel().openName.value);
		return problem;
	}

	const dispatcher = createDispatcher({
		transport: { on: onSpaSocketEvent, call: baseCall },
		handlers: { take_screenshot: (params) => takePageScreenshot(params, askedAbout.get(params)) },
		// The chat app's turns only; an older AR names no client and never offers the chat app a tool.
		ownsCall: (call) => call?.client_type === SPA_CLIENT_TYPE && useChatStore().isOwnLiveTurn(call.session_id),
		// The widget's other tools may reach this room; they are the widget's to answer.
		ignoreUnknownTools: true,
		confirmTools: new Set(["take_screenshot"]),
		trustKey: (toolName) => `${getSessionId()}|${usePagePanel().openName.value}|${toolName}`,
		describe: () => __("The page open beside the chat"),
		// With nothing to capture, answer at once rather than ask the user to approve nothing.
		preflight,
		confirm: (request) => askConfirm({ ...request, copy: pageCopy() }),
		getSessionId,
	});

	// No drain of the pending queue: the socket is in the room before this tab sends a turn, and
	// draining would take calls queued for a Desk widget.
	onMounted(() => dispatcher.start());
	onBeforeUnmount(() => dispatcher.stop());
}
