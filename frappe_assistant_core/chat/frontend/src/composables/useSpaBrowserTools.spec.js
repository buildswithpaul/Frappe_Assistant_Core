import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";

const h2c = vi.hoisted(() => ({ calls: [] }));
vi.mock("html2canvas-pro", () => ({
	default: async (el, options) => {
		h2c.calls.push({ el, options });
		return { width: 640, height: 480, toBlob: (cb, type) => cb(new Blob(["jpeg"], { type })) };
	},
}));

const baseCall = vi.hoisted(() => vi.fn(async () => null));
vi.mock("@/api/_core", () => ({ baseCall, getCall: vi.fn() }));

const uploadFile = vi.hoisted(() => vi.fn());
vi.mock("@/api/domains/chat", () => ({ chat: { uploadFile } }));

const socket = vi.hoisted(() => ({ listeners: {} }));
vi.mock("@/composables/useStreaming", () => ({
	onSpaSocketEvent: (event, fn) => {
		socket.listeners[event] = fn;
		return () => delete socket.listeners[event];
	},
}));

import { RESULT_METHOD } from "@/utils/browserToolDispatch";
import { confirms, resetConfirms, settleConfirm } from "@/widget/panel/confirmQueue";
import { usePagePanel } from "./usePagePanel";
import { takePageScreenshot, useSpaBrowserTools } from "./useSpaBrowserTools";

const NO_PAGE = "No page is open in the panel.";

let hide = () => {};
let wrapper;
let pageElement;

function showPage({ draft = false } = {}) {
	pageElement = document.createElement(draft ? "iframe" : "div");
	hide = usePagePanel().showPageView({ element: pageElement, draft });
}

beforeEach(() => {
	h2c.calls = [];
	baseCall.mockClear();
	uploadFile.mockReset().mockResolvedValue({ file_url: "/private/files/shot.jpg", file_name: "shot.jpg" });
});
afterEach(() => {
	hide();
	wrapper?.unmount();
	wrapper = null;
	resetConfirms();
});

describe("takePageScreenshot", () => {
	it("returns the error, and captures nothing, with no page open", async () => {
		expect(await takePageScreenshot({})).toEqual({ error: NO_PAGE });
		expect(h2c.calls).toEqual([]);
		expect(uploadFile).not.toHaveBeenCalled();
	});

	it("uploads one image of the open page's element, whatever selector it is given", async () => {
		showPage();
		const result = await takePageScreenshot({ selector: "#elsewhere", quality: 70 });

		expect(h2c.calls).toHaveLength(1);
		expect(h2c.calls[0].el).toBe(pageElement);
		expect(h2c.calls[0].options.allowTaint).toBe(false);
		expect(uploadFile).toHaveBeenCalledTimes(1);
		const file = uploadFile.mock.calls[0][0];
		expect(file).toBeInstanceOf(File);
		expect(file.type).toBe("image/jpeg");
		expect(result).toMatchObject({
			success: true,
			file_url: "/private/files/shot.jpg",
			width: 640,
			height: 480,
			mime_type: "image/jpeg",
		});
	});

	it("says a draft's preview cannot be captured", async () => {
		showPage({ draft: true });
		const result = await takePageScreenshot({});
		expect(result.error).toMatch(/draft/i);
		expect(h2c.calls).toEqual([]);
	});

	it("reports a failed upload as an error", async () => {
		showPage();
		uploadFile.mockRejectedValue(new Error("too big"));
		expect((await takePageScreenshot({})).error).toMatch(/too big/);
	});
});

describe("useSpaBrowserTools", () => {
	const Host = defineComponent({
		setup() {
			useSpaBrowserTools({ getSessionId: () => "s1" });
			return () => h("div");
		},
	});
	const call = (call_id) =>
		socket.listeners.faco_browser_tool_call({ call_id, session_id: "s1", tool_name: "take_screenshot", params: {} });
	const results = () => baseCall.mock.calls.filter(([method]) => method === RESULT_METHOD).map(([, args]) => args);

	it("answers at once, without asking, when no page is open", async () => {
		wrapper = mount(Host);
		await call("c1");
		expect(confirms.value).toEqual([]);
		expect(results()).toEqual([{ call_id: "c1", error: NO_PAGE }]);
	});

	it("answers a draft at once too, without asking", async () => {
		showPage({ draft: true });
		wrapper = mount(Host);
		await call("c3");
		expect(confirms.value).toEqual([]);
		expect(results()[0].error).toMatch(/draft/i);
	});

	it("leaves a call without a session to the Desk widget", async () => {
		wrapper = mount(Host);
		await socket.listeners.faco_browser_tool_call({ call_id: "c4", tool_name: "take_screenshot", params: {} });
		expect(baseCall.mock.calls.map(([method]) => method.split(".").pop())).toEqual([
			"get_pending_browser_tool_calls",
		]);
	});

	it("asks first, then captures the open page once the user approves", async () => {
		showPage();
		wrapper = mount(Host);
		const pending = call("c2");
		await flushPromises();
		expect(confirms.value).toHaveLength(1);
		expect(confirms.value[0].request.tool_name).toBe("take_screenshot");
		expect(uploadFile).not.toHaveBeenCalled();

		settleConfirm(confirms.value[0], "approve");
		await pending;
		expect(h2c.calls[0].el).toBe(pageElement);
		expect(results()[0]).toMatchObject({ call_id: "c2", result: { file_url: "/private/files/shot.jpg" } });
	});

	it("stops listening when its host unmounts", () => {
		wrapper = mount(Host);
		expect(socket.listeners.faco_browser_tool_call).toBeTypeOf("function");
		wrapper.unmount();
		wrapper = null;
		expect(socket.listeners.faco_browser_tool_call).toBeUndefined();
	});
});
