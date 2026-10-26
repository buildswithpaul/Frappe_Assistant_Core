import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";

// The Desk widget and the chat app can hold the same conversation. Both sit in its
// task_progress room, so both receive every browser tool call for it; each must answer only
// the calls its own turns made, or the first answer, from the wrong client, wins.

vi.mock("html2canvas-pro", () => ({
	default: async () => ({ width: 1, height: 1, toBlob: (cb, type) => cb(new Blob(["jpeg"], { type })) }),
}));

const baseCall = vi.hoisted(() => vi.fn(async () => null));
vi.mock("@/api/_core", () => ({ baseCall, getCall: vi.fn(), getCsrfToken: () => "" }));
vi.mock("@/api/domains/chat", () => ({
	chat: { uploadFile: vi.fn(async () => ({ file_url: "/private/files/page.jpg", file_name: "page.jpg" })) },
}));

const spa = vi.hoisted(() => ({ listeners: {} }));
vi.mock("@/composables/useStreaming", () => ({
	onSpaSocketEvent: (event, fn) => {
		spa.listeners[event] = fn;
		return () => delete spa.listeners[event];
	},
}));
// This tab sent the live turn: chatStore.isOwnLiveTurn has its own spec. No turn was taken over.
vi.mock("@/stores/chatStore", () => ({
	useChatStore: () => ({ isOwnLiveTurn: () => true, isClaimedLiveTurn: () => false, claimedTurnSession: null }),
}));

import widgetTools, { startBrowserTools, stopBrowserTools } from "@/widget/desk/browserTools";
import { confirms, resetConfirms, settleConfirm } from "@/widget/panel/confirmQueue";
import { usePagePanel } from "./usePagePanel";
import { useSpaBrowserTools } from "./useSpaBrowserTools";

const RESULT = "submit_browser_tool_result";

let widgetListener;
let widgetCalls;
let wrapper;
let hidePage;

beforeEach(() => {
	widgetCalls = [];
	baseCall.mockClear();
	globalThis.frappe = {
		get_route: () => [],
		realtime: { socket: {}, on: (event, fn) => event === "faco_browser_tool_call" && (widgetListener = fn) },
		call: vi.fn(async ({ method, args }) => {
			widgetCalls.push({ name: method.split(".").pop(), args });
			return { message: [] };
		}),
	};
	vi.spyOn(widgetTools.handlers, "take_screenshot").mockResolvedValue({ success: true, file_url: "/desk.jpg" });
	startBrowserTools({ getSessionId: () => "s1", confirm: async () => "approve" });

	usePagePanel().open("sales-a1b2c3");
	hidePage = usePagePanel().showPageView({ element: document.createElement("div"), draft: false });
	wrapper = mount(
		defineComponent({
			setup() {
				useSpaBrowserTools({ getSessionId: () => "s1" });
				return () => h("div");
			},
		}),
	);
});

afterEach(() => {
	wrapper.unmount();
	hidePage();
	usePagePanel().close();
	resetConfirms();
	stopBrowserTools();
	widgetTools._initialized = false;
	vi.restoreAllMocks();
});

const deliver = (call) => [widgetListener(call), spa.listeners.faco_browser_tool_call(call)];
const shot = (call_id, client_type) => ({
	call_id,
	session_id: "s1",
	client_type,
	tool_name: "take_screenshot",
	params: {},
});
const widgetResults = () => widgetCalls.filter((c) => c.name === RESULT);
const spaResults = () => baseCall.mock.calls.filter(([method]) => method.endsWith(RESULT));

describe("one conversation open in the widget and the chat app", () => {
	it("leaves a widget turn's screenshot to the widget", async () => {
		await Promise.all(deliver(shot("w1", "widget")));
		expect(widgetResults()).toHaveLength(1);
		expect(widgetResults()[0].args.result.file_url).toBe("/desk.jpg");
		expect(baseCall).not.toHaveBeenCalled();
		expect(confirms.value).toEqual([]);
	});

	it("leaves a widget turn's page context to the widget, which the chat app has no handler for", async () => {
		vi.spyOn(widgetTools.handlers, "get_page_context").mockResolvedValue({ page_type: "list" });
		await Promise.all(deliver({ ...shot("w2", "widget"), tool_name: "get_page_context" }));
		expect(widgetResults()).toHaveLength(1);
		expect(baseCall).not.toHaveBeenCalled();
	});

	it("leaves a chat app turn's screenshot to the chat app", async () => {
		const pending = deliver(shot("s1", "spa"));
		await flushPromises();
		settleConfirm(confirms.value[0], "approve");
		await Promise.all(pending);
		expect(widgetCalls).toEqual([]);
		expect(widgetTools.handlers.take_screenshot).not.toHaveBeenCalled();
		expect(spaResults()).toHaveLength(1);
		expect(spaResults()[0][1].result.file_url).toBe("/private/files/page.jpg");
	});
});
