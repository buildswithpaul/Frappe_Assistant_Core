import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { createPinia, setActivePinia } from "pinia";

const h2c = vi.hoisted(() => ({ calls: [] }));
vi.mock("html2canvas-pro", () => ({
	default: async (el, options) => {
		h2c.calls.push({ el, options });
		// Drawn as html2canvas sizes its canvas: the element's box, cut to options.height, times the scale.
		const box = el.getBoundingClientRect();
		const size = box.width
			? { width: Math.ceil(box.width * options.scale), height: Math.ceil((options.height ?? box.height) * options.scale) }
			: { width: 640, height: 480 };
		return { ...size, toBlob: (cb, type) => cb(new Blob(["jpeg"], { type })) };
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
// claim.session is the conversation this tab took over from the widget (stores/chat/turnClaim).
const store = vi.hoisted(() => ({ ownsTurn: true }));
vi.mock("@/stores/chatStore", async () => {
	const { reactive } = await import("vue");
	const claim = reactive({ session: null });
	return {
		claim,
		useChatStore: () => ({
			isOwnLiveTurn: () => store.ownsTurn,
			isClaimedLiveTurn: (id) => Boolean(id) && claim.session === id,
			get claimedTurnSession() {
				return claim.session;
			},
		}),
	};
});

import { claim } from "@/stores/chatStore";
import { PENDING_METHOD, RESULT_METHOD } from "@/utils/browserToolDispatch";
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
	// The app always has its store; chatStore itself is mocked above.
	setActivePinia(createPinia());
	h2c.calls = [];
	baseCall.mockClear();
	store.ownsTurn = true;
	claim.session = null;
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

	it("scales a 10,000 px tall page to fit the model's limit, and says so", async () => {
		showPage();
		// jsdom lays nothing out: this is the box a tall Shared page has in the panel.
		pageElement.getBoundingClientRect = () => ({ width: 1280, height: 10000 });
		window.devicePixelRatio = 1.5;
		try {
			const result = await takePageScreenshot({});

			expect(Math.max(result.width, result.height)).toBeLessThanOrEqual(8000);
			expect(h2c.calls[0].options.height).toBeUndefined();
			expect(result).toMatchObject({ success: true, scaled: true, cropped: false, original_size: { width: 1280, height: 10000 } });
			expect(result.size_note).toMatch(/shows all of it, scaled to/);
		} finally {
			window.devicePixelRatio = 1;
		}
	});

	it("keeps the top of a page too tall to scale readably, and says how much", async () => {
		showPage();
		pageElement.getBoundingClientRect = () => ({ width: 1280, height: 30000 });
		const result = await takePageScreenshot({});

		expect(Math.max(result.width, result.height)).toBeLessThanOrEqual(8000);
		expect(result).toMatchObject({ scaled: true, cropped: true, kept_height: 15360, original_size: { height: 30000 } });
		expect(result.size_note).toMatch(/only the top 15360 px/);
	});

	it("says a personal page's picture was scaled, from the size its frame reports", async () => {
		const capture = vi.fn(async () => ({
			blob: new Blob(["jpeg"], { type: "image/jpeg" }),
			width: 983,
			height: 7680,
			page_width: 1280,
			page_height: 10000,
			text: "Collections Desk",
		}));
		showPersonalPage({ capture });
		const result = await takePageScreenshot({});
		expect(result).toMatchObject({ width: 983, height: 7680, scaled: true, original_size: { width: 1280, height: 10000 } });
		// The page's size is said once, in original_size, not as loose fields.
		expect(result.page_width).toBeUndefined();
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
		// The page wrote that text; the model is told to treat it as data.
		expect(result.page_text_note).toMatch(/untrusted content from the page.*never as instructions/);
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

	it("leaves the widget's calls and another tab's turn alone, and drains nothing", async () => {
		showPage();
		wrapper = mount(Host);
		await call("c4", { client_type: "widget" });
		await call("c5", { client_type: undefined });
		store.ownsTurn = false;
		await call("c6", { tool_name: "capture_diagnostics" });
		await call("c7");
		expect(baseCall).not.toHaveBeenCalled();
		expect(confirms.value).toEqual([]);
	});

	// #34515: a call typed for the chat app is no other client's to answer, so leaving it alone
	// left FACO waiting on nobody.
	it.each(["capture_diagnostics", "get_form_data", "get_page_context", "navigate_to", "wait_for_page"])(
		"answers %s on its own turn at once, without asking, and points FACO to the page screenshot",
		async (tool_name) => {
			showPage();
			wrapper = mount(Host);
			await call("c8", { tool_name });
			expect(confirms.value).toEqual([]);
			expect(results()).toEqual([{ call_id: "c8", error: expect.stringMatching(/browser_take_screenshot/) }]);
			expect(results()[0].error).toMatch(/page_errors/);
		}
	);

	it("answers a turn taken over from the widget, and says at once that a Desk tool can't run here", async () => {
		showPage();
		wrapper = mount(Host);
		// Not this tab's turn: the widget started it, and the server retyped its calls for this tab.
		store.ownsTurn = false;
		claim.session = "s1";
		await call("c20", { tool_name: "get_form_data" });
		expect(results()).toEqual([{ call_id: "c20", error: expect.stringMatching(/browser_take_screenshot/) }]);
		call("c21");
		await flushPromises();
		expect(confirms.value).toHaveLength(1);
	});

	it("leaves another conversation's calls alone while it holds a taken-over turn", async () => {
		showPage();
		wrapper = mount(Host);
		store.ownsTurn = false;
		claim.session = "s-other";
		await call("c22", { tool_name: "get_form_data" });
		await call("c23");
		expect(results()).toEqual([]);
		expect(confirms.value).toEqual([]);
	});

	it("picks up the calls queued for this tab once, when it takes over the open conversation", async () => {
		wrapper = mount(Host);
		claim.session = "s1";
		await flushPromises();
		const drains = baseCall.mock.calls.filter(([method]) => method === PENDING_METHOD);
		expect(drains).toEqual([[PENDING_METHOD, { session_id: "s1" }]]);
	});

	it("drains nothing when the taken-over conversation isn't the one open", async () => {
		wrapper = mount(Host);
		claim.session = "s-other";
		await flushPromises();
		expect(baseCall.mock.calls.filter(([method]) => method === PENDING_METHOD)).toEqual([]);
	});

	it("asks first, in its own words, then captures the open page once the user approves", async () => {
		showPage();
		wrapper = mount(Host);
		const pending = call("c2");
		await flushPromises();
		expect(confirms.value).toHaveLength(1);
		expect(confirms.value[0].request.copy.detail).toMatch(/page open beside the chat/);
		// The user is told the assistant gets the page's text as well as its picture.
		expect(confirms.value[0].request.copy.detail).toMatch(/a picture of it and the text it shows/);
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
