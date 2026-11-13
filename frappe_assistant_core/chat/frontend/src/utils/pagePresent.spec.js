import { afterEach, describe, expect, it, vi } from "vitest";

import { makePresenter, mountPresentControls, presentKey, remoteDeck } from "./pagePresent";

const PAGE = `<div class="fac-page-root">
	<section class="mk-section" data-title="Company"><button class="mk-edit">Edit</button></section>
	<section class="mk-section"><h3>Finance</h3></section>
	<section class="mk-section" data-title="Decathlon"></section>
</div>`;

function page(html = PAGE) {
	const host = document.createElement("div");
	host.innerHTML = html;
	document.body.append(host);
	return host;
}

afterEach(() => {
	document.body.replaceChildren();
	delete document.fullscreenElement;
});

const off = (root) => [...root.querySelectorAll(".mk-section")].map((s) => s.classList.contains("fac-present-off"));

describe("makePresenter", () => {
	it("shows the first section and names every section", () => {
		const root = page();
		const state = makePresenter(root).start();
		expect(state).toEqual({ index: 0, count: 3, titles: ["Company", "Finance", "Decathlon"] });
		expect(off(root)).toEqual([false, true, true]);
		expect(root.querySelector(".fac-page-root").classList.contains("fac-presenting")).toBe(true);
	});

	it("moves to a section, kept within the page's sections", () => {
		const root = page();
		const deck = makePresenter(root);
		deck.start();
		expect(deck.show(5).index).toBe(2);
		expect(off(root)).toEqual([true, true, false]);
		expect(deck.show(-3).index).toBe(0);
	});

	it("puts the page back as it was when it stops", () => {
		const root = page();
		const deck = makePresenter(root);
		deck.start();
		deck.show(1);
		deck.stop();
		expect(off(root)).toEqual([false, false, false]);
		expect(root.querySelector(".fac-presenting")).toBeNull();
	});

	it("presents a page without sections as one screen", () => {
		const root = page('<div class="fac-page-root"><p>All of it</p></div>');
		const deck = makePresenter(root);
		expect(deck.start()).toMatchObject({ index: 0, count: 1 });
		expect(deck.show(1).index).toBe(0);
	});

	it("works inside a shadow root, where a shared page lives", () => {
		const host = document.createElement("div");
		document.body.append(host);
		const shadow = host.attachShadow({ mode: "open" });
		shadow.innerHTML = PAGE;
		expect(makePresenter(shadow).start().count).toBe(3);
		expect(off(shadow)).toEqual([false, true, true]);
	});
});

describe("presentKey", () => {
	const key = (k, extra = {}) => presentKey({ key: k, target: document.body, ...extra });

	it("maps the presenting keys", () => {
		expect(["ArrowRight", "ArrowDown", "PageDown", " "].map((k) => key(k))).toEqual(["next", "next", "next", "next"]);
		expect(["ArrowLeft", "ArrowUp", "PageUp"].map((k) => key(k))).toEqual(["prev", "prev", "prev"]);
		expect([key("Home"), key("End"), key("Escape"), key("a")]).toEqual(["first", "last", "exit", null]);
	});

	it("leaves typing alone", () => {
		const input = document.createElement("textarea");
		expect(presentKey({ key: "ArrowRight", target: input })).toBeNull();
		expect(key("ArrowRight", { ctrlKey: true })).toBeNull();
	});
});

describe("mountPresentControls", () => {
	function fakeDeck() {
		const calls = [];
		const titles = ["Company", "<b>Finance</b>", "Decathlon"];
		return {
			calls,
			start: () => (calls.push(["start"]), { index: 0, count: 3, titles }),
			show: (i) => (calls.push(["show", i]), { index: Math.max(0, Math.min(2, i)), count: 3, titles }),
			stop: () => calls.push(["stop"]),
		};
	}
	const where = (container) => container.querySelector(".fac-present-where").textContent;

	it("draws the controls and moves through the sections", async () => {
		const container = page();
		const deck = fakeDeck();
		await mountPresentControls({ container, deck, fullscreen: false });
		expect(container.classList.contains("fac-present-container")).toBe(true);
		expect(where(container)).toBe("1 / 3 · Company");
		container.querySelector(".fac-present-next").click();
		await Promise.resolve();
		expect(deck.calls).toContainEqual(["show", 1]);
		expect(where(container)).toBe("2 / 3 · <b>Finance</b>");
		expect(container.querySelector(".fac-present-where b")).toBeNull();
	});

	it("gives the container a page background while presenting, and puts its style back after", async () => {
		// The container sits outside the page's shadow root, where the kit's styles do not reach,
		// so full screen would otherwise show the browser's black backdrop.
		const container = page();
		container.style.padding = "3px";
		const presenting = await mountPresentControls({ container, deck: fakeDeck(), fullscreen: false });
		expect(container.style.background).toBe("rgb(255, 255, 255)");
		expect(container.style.overflow).toBe("auto");
		await presenting.stop();
		expect(container.style.background).toBe("");
		expect(container.style.padding).toBe("3px");
	});

	it("gives the container the kit's dark background when Desk is dark", async () => {
		document.documentElement.setAttribute("data-theme", "dark");
		const container = page();
		await mountPresentControls({ container, deck: fakeDeck(), fullscreen: false });
		expect(container.style.background).toBe("rgb(23, 23, 23)");
		document.documentElement.removeAttribute("data-theme");
	});

	it("moves with the keyboard and stops with Escape", async () => {
		const container = page();
		const deck = fakeDeck();
		const onExit = vi.fn();
		await mountPresentControls({ container, deck, onExit, fullscreen: false });
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
		await Promise.resolve();
		expect(where(container)).toBe("2 / 3 · <b>Finance</b>");
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		await Promise.resolve();
		await Promise.resolve();
		expect(deck.calls.at(-1)).toEqual(["stop"]);
		expect(container.querySelector(".fac-present-bar")).toBeNull();
		expect(container.classList.contains("fac-present-container")).toBe(false);
		expect(onExit).toHaveBeenCalled();
	});

	it("asks for full screen, and still presents when that is refused or missing", async () => {
		const container = page();
		container.requestFullscreen = vi.fn(() => Promise.reject(new Error("denied")));
		await mountPresentControls({ container, deck: fakeDeck() });
		expect(container.requestFullscreen).toHaveBeenCalled();
		expect(container.querySelector(".fac-present-bar")).not.toBeNull();
		const bare = page();
		await mountPresentControls({ container: bare, deck: fakeDeck() });
		expect(bare.querySelector(".fac-present-bar")).not.toBeNull();
	});

	it("stops when the browser leaves full screen", async () => {
		const container = page();
		container.requestFullscreen = vi.fn(() => {
			document.fullscreenElement = container;
			return Promise.resolve();
		});
		const deck = fakeDeck();
		await mountPresentControls({ container, deck });
		document.fullscreenElement = null;
		document.dispatchEvent(new Event("fullscreenchange"));
		await Promise.resolve();
		await Promise.resolve();
		expect(deck.calls.at(-1)).toEqual(["stop"]);
		expect(container.querySelector(".fac-present-bar")).toBeNull();
	});
});

describe("Present mode, from the review", () => {
	const fakeDeck = () => {
		const calls = [];
		const titles = ["A", "B", "C"];
		return {
			calls,
			start: () => (calls.push(["start"]), { index: 0, count: 3, titles }),
			show: (i) => (calls.push(["show", i]), { index: i, count: 3, titles }),
			stop: () => calls.push(["stop"]),
		};
	};

	it("leaves typing in a field inside a shared page's shadow root alone", async () => {
		const container = page('<div class="host"></div>');
		const shadow = container.querySelector(".host").attachShadow({ mode: "open" });
		shadow.innerHTML = "<select><option>NOV</option><option>OCT</option></select>";
		const deck = fakeDeck();
		await mountPresentControls({ container, deck, fullscreen: false });
		shadow.querySelector("select").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, composed: true }));
		await Promise.resolve();
		expect(deck.calls.some(([call]) => call === "show")).toBe(false);
	});

	it("covers the screen and pins the bar to its foot, then puts the container back", async () => {
		const container = page();
		container.style.cssText = "contain: layout paint; overflow: clip;";
		const before = container.style.cssText;
		const presenting = await mountPresentControls({ container, deck: fakeDeck(), fullscreen: false });
		expect(container.style.position).toBe("fixed");
		expect(container.style.overflow).toBe("auto");
		expect(container.querySelector(".fac-present-bar").style.position).toBe("sticky");
		expect(presenting.active).toBe(true);
		await presenting.stop();
		expect(presenting.active).toBe(false);
		expect(container.style.cssText).toBe(before);
	});

	it("tells a personal page's frame to stop when its start failed, so it is not left half-presented", async () => {
		const sent = [];
		const frame = {
			present: (command) => {
				sent.push(command);
				return command === "start" ? Promise.reject(new Error("The page did not answer.")) : Promise.resolve(null);
			},
		};
		await expect(remoteDeck(frame).start()).rejects.toThrow("did not answer");
		expect(sent).toEqual(["start", "stop"]);
	});
});
