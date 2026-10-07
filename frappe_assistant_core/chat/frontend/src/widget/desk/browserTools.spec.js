import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const h2c = vi.hoisted(() => ({ options: null, overlayDuringCapture: null, fail: false }));
vi.mock("html2canvas-pro", () => ({
	default: async (_el, options) => {
		h2c.options = options;
		h2c.overlayDuringCapture = document.getElementById("fac-screenshot-overlay");
		if (h2c.fail) throw new Error("capture exploded");
		return { width: 1, height: 1, toBlob: (cb) => cb(null) };
	},
}));
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// startBrowserTools polls for the realtime socket for 10 s and registers its listener once per
// module, so a test that starts it must not leave either behind for the next test or the runner.
afterEach(async () => {
	const tools = await import("./browserTools.js");
	tools.stopBrowserTools();
	tools.default._initialized = false;
});

const toolsJs = resolve(process.cwd(), "src/widget/desk/browserTools.js");
const src = () => readFileSync(toolsJs, "utf8");

/**
 * The widget half of the browser-tool budget contract. The server suspends its
 * short delivery deadline only while the widget says a human is deciding, so if
 * these reports stop being emitted — or are emitted in the wrong order —
 * screenshots silently go back to timing out mid-approval.
 */
describe("browser tool progress reports", () => {
	it("reports receipt before doing anything else", () => {
		const handler = src().match(/async _handleToolCall\(data\) \{([\s\S]*?)\n\t\},/);
		expect(handler).not.toBeNull();
		expect(handler[1]).toMatch(/report_progress\(call_id, "received"\)/);
	});

	it("reports awaiting_user BEFORE blocking on the approval card", () => {
		const body = src();
		const awaitingAt = body.indexOf('report_progress(call_id, "awaiting_user")');
		const confirmAt = body.indexOf("await this._requestUserConfirmation(");

		expect(awaitingAt).toBeGreaterThan(-1);
		expect(confirmAt).toBeGreaterThan(-1);
		expect(awaitingAt).toBeLessThan(confirmAt);
	});

	it("reports executing before running the handler", () => {
		const body = src();
		const executingAt = body.indexOf('report_progress(call_id, "executing")');
		const handlerAt = body.indexOf("await handler.call(this.handlers,");

		expect(executingAt).toBeGreaterThan(-1);
		expect(executingAt).toBeLessThan(handlerAt);
	});

	it("does not await progress reports — they must never gate execution", () => {
		const body = src();
		expect(body).not.toMatch(/await this\.report_progress/);
	});

	it("targets the ack endpoint the server actually exposes", () => {
		expect(src()).toMatch(/browser_bridge\.submit_browser_tool_ack/);
	});
});

describe("capture library", () => {
	it("bundles html2canvas-pro, never the unmaintained 1.4.1", () => {
		const pkg = JSON.parse(readFileSync(resolve(process.cwd(), "package.json"), "utf8"));
		expect(pkg.dependencies["html2canvas-pro"]).toBe("2.3.8");
		expect(pkg.dependencies.html2canvas).toBeUndefined();
		expect(src()).toMatch(/import\("html2canvas-pro"\)/);
	});
});

describe("screenshot capture bounds", () => {
	it("caps devicePixelRatio scaling", () => {
		const body = src();
		expect(body).toMatch(/scale: Math\.min\(window\.devicePixelRatio \|\| 1, MAX_SCREENSHOT_SCALE\)/);
		expect(body).toMatch(/const MAX_SCREENSHOT_SCALE = 1\.5/);
	});

	it("overrides html2canvas' 15s-per-image default", () => {
		const body = src();
		expect(body).toMatch(/imageTimeout: SCREENSHOT_IMAGE_TIMEOUT_MS/);
		const value = body.match(/const SCREENSHOT_IMAGE_TIMEOUT_MS = (\d+)/);
		expect(value).not.toBeNull();
		expect(Number(value[1])).toBeLessThan(15000);
	});

	it("caps full-page height", () => {
		expect(src()).toMatch(
			/Math\.min\(document\.body\.scrollHeight, MAX_SCREENSHOT_HEIGHT_PX\)/
		);
	});

	it("does not allow tainting — toBlob throws on a tainted canvas", () => {
		expect(src()).toMatch(/allowTaint: false/);
		expect(src()).not.toMatch(/allowTaint: true/);
	});

	it("handles the null blob an oversized canvas produces", () => {
		// Without this, `new File([null])` uploads the 4-byte string "null" and
		// the upload endpoint rejects it as a magic-byte mismatch.
		const body = src();
		const blobAt = body.indexOf("canvas.toBlob(resolve");
		const guardAt = body.indexOf("if (!blob)");

		expect(guardAt).toBeGreaterThan(blobAt);
		expect(body.slice(guardAt, guardAt + 400)).toMatch(/Screenshot too large/);
	});
});

describe("a call arriving while the panel is closed", () => {
	it("acknowledges receipt first, then asks to open the panel for confirmation", async () => {
		const handlers = {};
		const calls = [];
		globalThis.frappe = {
			realtime: { socket: { connected: true }, on: (e, fn) => (handlers[e] = fn) },
			call: vi.fn(async ({ method, args }) => {
				calls.push([method.split(".").pop(), args && args.state]);
				return { message: [] };
			}),
		};
		const { startBrowserTools } = await import("./browserTools.js");
		const confirm = vi.fn(async () => "deny");
		startBrowserTools({ getSessionId: () => "s1", confirm });
		await handlers.faco_browser_tool_call({ call_id: "c1", session_id: "s1", tool_name: "take_screenshot", params: {} });
		expect(calls[0]).toEqual(["submit_browser_tool_ack", "received"]);
		expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ tool_name: "take_screenshot" }));
	});
});

describe("get_page_context honours the DOM-extraction privacy switch", () => {
	let pageContext;
	let tools;
	let jq;
	beforeEach(async () => {
		vi.resetModules(); // deps live at module scope; each case starts from the defaults
		globalThis.frappe = { get_route: () => [] };
		jq = vi.fn(() => {
			throw new Error("DOM must not be read");
		});
		window.$ = jq;
		const mod = await import("./browserTools.js");
		tools = mod;
		pageContext = (await import("./pageContext.js")).default;
	});
	afterEach(() => {
		vi.restoreAllMocks();
		delete window.$;
	});

	it("extracts no DOM when the operator switched it off", async () => {
		tools.startBrowserTools({
			getWidgetSettings: () => ({ privacy: { enable_dom_extraction: false } }),
		});
		const result = await tools.default.handlers.get_page_context();
		expect(jq).not.toHaveBeenCalled();
		expect(result.dom_content).not.toMatch(/Visible Text|Structured Data/);
	});

	it("does not extract by default, before the launcher supplies settings", async () => {
		tools.startBrowserTools({});
		await tools.default.handlers.get_page_context();
		expect(jq).not.toHaveBeenCalled();
	});

	it("attempts extraction, with the settings it was given, when enabled", async () => {
		const settings = { privacy: { enable_dom_extraction: true } };
		const spy = vi.spyOn(pageContext, "extract_screen_content").mockResolvedValue("EXTRACTED");
		tools.startBrowserTools({ getWidgetSettings: () => settings });
		const result = await tools.default.handlers.get_page_context();
		expect(spy).toHaveBeenCalledWith(expect.anything(), settings);
		expect(result.dom_content).toBe("EXTRACTED");
	});
});

describe("take_screenshot hides the widget hosts from the capture", () => {
	it("hides both shadow hosts, the capture overlay and the legacy widget in the clone", async () => {
		const { default: tools } = await import("./browserTools.js");
		await tools.handlers.take_screenshot({});
		const els = {};
		const sel = ["#fac-widget-launcher", "#fac-widget-panel", "#fac-screenshot-overlay", ".faco-widget"];
		sel.forEach((q) => (els[q] = { style: {} }));
		h2c.options.onclone({ querySelector: (q) => els[q] || null });
		sel.forEach((q) => expect(els[q].style.display).toBe("none"));
	});

	it("shows its overlay only while capturing", async () => {
		const { default: tools } = await import("./browserTools.js");
		h2c.overlayDuringCapture = null;
		await tools.handlers.take_screenshot({});
		expect(h2c.overlayDuringCapture).not.toBeNull();
		expect(document.getElementById("fac-screenshot-overlay")).toBeNull();
	});

	it("removes its overlay even when the capture throws", async () => {
		const { default: tools } = await import("./browserTools.js");
		h2c.fail = true;
		try {
			const result = await tools.handlers.take_screenshot({});
			expect(result.error).toMatch(/capture exploded/);
		} finally {
			h2c.fail = false;
		}
		expect(h2c.overlayDuringCapture).not.toBeNull();
		expect(document.getElementById("fac-screenshot-overlay")).toBeNull();
	});
});

describe("the confirmation gate fails closed", () => {
	let tools;
	let calls;
	let run;
	const DECLINED = /declined/;

	beforeEach(async () => {
		vi.resetModules();
		calls = [];
		globalThis.frappe = {
			get_route: () => [],
			realtime: { socket: {}, on: () => {} },
			call: vi.fn(async ({ method, args }) => {
				calls.push({ name: method.split(".").pop(), args });
				return { message: [] };
			}),
		};
		tools = (await import("./browserTools.js")).default;
		run = vi.spyOn(tools.handlers, "take_screenshot").mockResolvedValue({ success: true });
	});
	afterEach(() => vi.restoreAllMocks());

	const start = async (confirm) => {
		(await import("./browserTools.js")).startBrowserTools({
			getSessionId: () => "s1",
			confirm,
		});
	};
	const call = (id, extra = {}) =>
		tools._handleToolCall({ call_id: id, tool_name: "take_screenshot", params: {}, ...extra });
	const submits = () => calls.filter((c) => c.name === "submit_browser_tool_result");

	it("denies and never runs the tool when confirm throws", async () => {
		await start(async () => {
			throw new Error("card crashed");
		});
		await call("a1");
		expect(run).not.toHaveBeenCalled();
		expect(submits()[0].args.error).toMatch(DECLINED);
	});

	it.each([undefined, null, "rejected", "Approve", ""])(
		"denies on the unexpected decision %j",
		async (decision) => {
			await start(async () => decision);
			await call("b1");
			expect(run).not.toHaveBeenCalled();
			expect(submits()[0].args.error).toMatch(DECLINED);
		}
	);

	it("runs on approve", async () => {
		await start(async () => "approve");
		await call("p1");
		expect(run).toHaveBeenCalledTimes(1);
	});

	it("trust runs the tool and is not asked again for the same tool", async () => {
		const confirm = vi.fn(async () => "trust");
		await start(confirm);
		await call("t1");
		await call("t2");
		expect(confirm).toHaveBeenCalledTimes(1);
		expect(run).toHaveBeenCalledTimes(2);
	});

	it("ignores a call addressed to another session: no ack, no prompt, no result", async () => {
		const confirm = vi.fn(async () => "approve");
		await start(confirm);
		await call("o1", { session_id: "other" });
		expect(calls).toEqual([]);
		expect(confirm).not.toHaveBeenCalled();
		expect(run).not.toHaveBeenCalled();
	});
});
