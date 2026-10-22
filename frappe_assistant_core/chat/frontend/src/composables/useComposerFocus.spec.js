import { describe, it, expect, afterEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { useComposerFocus, COMPOSER_FOCUSED_CLASS } from "./useComposerFocus.js";

// Redmine #34380: with a phone keyboard open the header, composer padding and home-indicator
// inset left the conversation a thin strip.
const root = document.documentElement;

function mountWithComposer() {
	const wrapper = mount(
		{
			setup() {
				useComposerFocus();
				return () => null;
			},
		},
		{ attachTo: document.body }
	);
	const box = document.createElement("div");
	box.className = "input-box";
	const composer = document.createElement("textarea");
	composer.className = "input-textarea";
	box.appendChild(composer);
	document.body.appendChild(box);
	return { wrapper, box, composer };
}

describe("useComposerFocus", () => {
	afterEach(() => {
		document.body.innerHTML = "";
		root.className = "";
	});

	it("marks the page while the composer has focus", () => {
		const { wrapper, composer } = mountWithComposer();
		composer.focus();
		expect(root.classList.contains(COMPOSER_FOCUSED_CLASS)).toBe(true);
		composer.blur();
		expect(root.classList.contains(COMPOSER_FOCUSED_CLASS)).toBe(false);
		wrapper.unmount();
	});

	it("ignores other fields", () => {
		const { wrapper } = mountWithComposer();
		const search = document.createElement("input");
		document.body.appendChild(search);
		search.focus();
		expect(root.classList.contains(COMPOSER_FOCUSED_CLASS)).toBe(false);
		wrapper.unmount();
	});

	it("drops the mark when the chat view goes away", () => {
		const { wrapper, composer } = mountWithComposer();
		composer.focus();
		wrapper.unmount();
		expect(root.classList.contains(COMPOSER_FOCUSED_CLASS)).toBe(false);
	});

	// jsdom has no visualViewport; on iOS it resizes when the keyboard opens.
	it("brings the whole composer back into view when the visible viewport shrinks", () => {
		const viewport = new EventTarget();
		vi.stubGlobal("visualViewport", viewport);
		const { wrapper, box, composer } = mountWithComposer();
		box.scrollIntoView = vi.fn();
		composer.focus();
		viewport.dispatchEvent(new Event("resize"));
		expect(box.scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
		wrapper.unmount();
		vi.unstubAllGlobals();
	});
});

// The collapse itself is CSS in three components; jsdom injects no scoped CSS, so read the source.
describe("phone layout while the composer has focus", () => {
	const __dirname = dirname(fileURLToPath(import.meta.url));
	const read = (p) => readFileSync(join(__dirname, p), "utf8");
	const phoneRules = (sfc) =>
		[...sfc.matchAll(/@media \(max-width: 640px\)\s*\{([\s\S]*?)\n\}/g)].map((m) => m[1]).join("\n");

	it("hides the header", () => {
		expect(phoneRules(read("../components/layout/TopBar.vue"))).toMatch(
			/:global\(html\.ql-composer-focused \.top-bar\)\s*\{\s*display:\s*none/
		);
	});

	it("drops the home-indicator inset the keyboard covers", () => {
		expect(phoneRules(read("../App.vue"))).toMatch(
			/:global\(html\.ql-composer-focused \.app-root\)\s*\{\s*padding-bottom:\s*0/
		);
	});

	it("trims the composer and caps a long draft", () => {
		const rules = phoneRules(read("../components/chat/InputArea.vue"));
		expect(rules).toMatch(/:global\(html\.ql-composer-focused \.input-area-container\)/);
		expect(rules).toMatch(/:global\(html\.ql-composer-focused \.input-textarea\)\s*\{\s*max-height/);
	});

	// `:global(.a) .b` compiles to `.a` alone in Vue's scoped CSS, which would hide the page.
	it("never scopes the class with the partial :global() form", () => {
		for (const file of ["../components/layout/TopBar.vue", "../App.vue", "../components/chat/InputArea.vue"]) {
			expect(read(file)).not.toMatch(/:global\(html\.ql-composer-focused\)\s/);
		}
	});

	it("is wired into the chat view", () => {
		expect(read("../views/ChatView.vue")).toMatch(/\nuseComposerFocus\(\);/);
	});
});
