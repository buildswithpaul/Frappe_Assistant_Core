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

// chatStore.isOwnLiveTurn has its own spec; here it says whether this tab sent the live turn.
const store = vi.hoisted(() => ({ ownsTurn: true }));
vi.mock("@/stores/chatStore", () => ({
	useChatStore: () => ({ isOwnLiveTurn: () => store.ownsTurn }),
}));

import { RESULT_METHOD } from "@/utils/browserToolDispatch";
import { confirms, resetConfirms, settleConfirm } from "@/widget/panel/confirmQueue";
import { usePagePanel } from "./usePagePanel";
import { takePageScreenshot, useSpaBrowserTools } from "./useSpaBrowserTools";

const NO_PAGE = "No page is open in the panel.";

let hide = () => {};
let wrapper;
let pageElement;
let session = "s1";

function showPage({ draft = false, errors = [] } = {}) {
	hide();
	pageElement = document.createElement(draft ? "iframe" : "div");
	hide = usePagePanel().showPageView({ element: pageElement, draft, errors: () => errors });
}

// A personal page: its frame draws itself and sends the picture back.
function showPersonalPage({ capture, errors = [] }) {
	hide();
	pageElement = null;
	hide = usePagePanel().showPageView({ capture, errors: () => errors });
}

beforeEach(() => {
	h2c.calls = [];
	baseCall.mockClear();
	store.ownsTurn = true;
	session = "s1";
	usePagePanel().open("sales-a1b2c3");
	uploadFile.mockReset().mockResolvedValue({ file_url: "/private/files/shot.jpg", file_name: "shot.jpg" });
});
afterEach(() => {
	hide();
	hide = () => {};
	wrapper?.unmount();
	wrapper = null;
	usePagePanel().close();
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

	it("tells FACO what went wrong while the page ran", async () => {
		showPage({ errors: ["frappe.client.get_list failed: Not permitted"] });
		expect((await takePageScreenshot({})).page_errors).toEqual(["frappe.client.get_list failed: Not permitted"]);
		showPage();
		expect((await takePageScreenshot({})).page_errors).toEqual([]);
	});

	it("draws a personal page's picture through its view, and uploads it", async () => {
		const capture = vi.fn(async () => ({
			blob: new Blob(["jpeg"], { type: "image/jpeg" }),
			width: 800,
			height: 600,
			text: "Sales 70,29,354",
		}));
		showPersonalPage({ capture, errors: ["boom"] });
		const result = await takePageScreenshot({ quality: 70 });
		expect(capture).toHaveBeenCalledWith(expect.objectContaining({ quality: 70 }));
		// The page lives in another origin: html2canvas never reads this document's copy of it.
		expect(h2c.calls).toEqual([]);
		const file = uploadFile.mock.calls[0][0];
		expect(file.type).toBe("image/jpeg");
		expect(result).toMatchObject({ success: true, width: 800, height: 600, page_errors: ["boom"], page_text: "Sales 70,29,354" });
	});

	it("still gives FACO the page's text and errors when the frame can't draw the picture", async () => {
		const failed = Object.assign(new Error("This browser can't capture the page."), { text: "Sales 70,29,354" });
		showPersonalPage({ capture: vi.fn(async () => Promise.reject(failed)), errors: ["boom"] });
		const result = await takePageScreenshot({});
		expect(result.error).toMatch(/can't capture the page/);
		expect(result).toMatchObject({ page_text: "Sales 70,29,354", page_errors: ["boom"] });
		expect(uploadFile).not.toHaveBeenCalled();
	});

	it("gives the visible text of a Shared page with its picture", async () => {
		showPage();
		pageElement.textContent = "Team planner 12 people";
		expect((await takePageScreenshot({})).page_text).toBe("Team planner 12 people");
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

	it("waits for a write that landed to redraw the page, then captures the new version", async () => {
		showPage();
		// usePagePanel bumps refreshKey when a write to the open page lands; PagePanel then refetches
		// and mounts a new PageView.
		usePagePanel().refreshKey.value++;
		const shot = takePageScreenshot({});
		// Longer than the animation frame a settled page waits for.
		await new Promise((resolve) => setTimeout(resolve, 60));
		expect(h2c.calls).toEqual([]);

		showPage();
		await shot;
		expect(h2c.calls).toHaveLength(1);
		expect(h2c.calls[0].el).toBe(pageElement);
	});
});

describe("useSpaBrowserTools", () => {
	const Host = defineComponent({
		setup() {
			useSpaBrowserTools({ getSessionId: () => session });
			return () => h("div");
		},
	});
	const call = (call_id, extra = {}) =>
		socket.listeners.faco_browser_tool_call({
			call_id,
			session_id: session,
			client_type: "spa",
			tool_name: "take_screenshot",
			params: {},
			...extra,
		});
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

	it("leaves the widget's calls, another tab's turn and tools it lacks alone, and drains nothing", async () => {
		showPage();
		wrapper = mount(Host);
		await call("c4", { client_type: "widget" });
		await call("c5", { client_type: undefined });
		await call("c6", { tool_name: "get_page_context" });
		store.ownsTurn = false;
		await call("c7");
		expect(baseCall).not.toHaveBeenCalled();
		expect(confirms.value).toEqual([]);
	});

	it("asks first, in its own words, then captures the open page once the user approves", async () => {
		showPage();
		wrapper = mount(Host);
		const pending = call("c2");
		await flushPromises();
		expect(confirms.value).toHaveLength(1);
		expect(confirms.value[0].request.copy.detail).toMatch(/page open beside the chat/);
		expect(uploadFile).not.toHaveBeenCalled();

		settleConfirm(confirms.value[0], "approve");
		await pending;
		expect(h2c.calls[0].el).toBe(pageElement);
		expect(results()[0]).toMatchObject({ call_id: "c2", result: { file_url: "/private/files/shot.jpg" } });
	});

	it("captures nothing when another page was opened while the user decided", async () => {
		showPage();
		wrapper = mount(Host);
		const pending = call("c9");
		await flushPromises();
		usePagePanel().open("another-page");
		showPage();
		settleConfirm(confirms.value[0], "approve");
		await pending;
		expect(h2c.calls).toEqual([]);
		expect(results()[0].error).toMatch(/Another page was opened/);
	});

	it.each(["trust", "trust_page"])("keeps %s to that page in that conversation", async (decision) => {
		showPage();
		wrapper = mount(Host);
		const trustOnce = async (id) => {
			const pending = call(id);
			await flushPromises();
			if (confirms.value.length) settleConfirm(confirms.value[0], decision);
			await pending;
		};
		const asked = () => baseCall.mock.calls.filter(([, args]) => args?.state === "awaiting_user").length;

		await trustOnce("t1");
		await trustOnce("t2");
		expect(asked()).toBe(1);

		usePagePanel().open("another-page");
		await trustOnce("t3");
		expect(asked()).toBe(2);

		session = "s2";
		await trustOnce("t4");
		expect(asked()).toBe(3);
	});

	it("offers the card no Always Allow wider than the page", async () => {
		showPage();
		wrapper = mount(Host);
		const pending = call("w1");
		await flushPromises();
		expect(confirms.value[0].request.alwaysAllow).toBe(false);
		settleConfirm(confirms.value[0], "deny");
		await pending;
	});

	it("denies a card still open when its host unmounts, and stops listening", async () => {
		showPage();
		wrapper = mount(Host);
		const pending = call("c8");
		await flushPromises();
		wrapper.unmount();
		wrapper = null;
		await pending;
		expect(results()[0].error).toMatch(/declined/);
		expect(socket.listeners.faco_browser_tool_call).toBeUndefined();
	});
});
