import { describe, it, expect, vi, afterEach } from "vitest";
import { isolateTyping } from "./keyIsolation.js";
import { bindShortcut } from "../launcher/shortcut.js";

// Frappe's `add_shortcut` handler: skip the key only when focus is reported on a field.
function deskShortcut(fire) {
	const handler = () => {
		if (document.activeElement?.matches("input, select, textarea, [contenteditable=true]")) return;
		fire();
	};
	window.addEventListener("keydown", handler);
	return () => window.removeEventListener("keydown", handler);
}

// The panel as mountPanel builds it: a host on <body> with the app inside an open shadow root.
function mountShadowPanel(inner) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	host.attachShadow({ mode: "open" }).innerHTML = inner;
	return host;
}

function press(el, init) {
	el.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, composed: true, ...init }));
}

describe("typing in the panel's fields", () => {
	const cleanups = [];
	afterEach(() => {
		cleanups.splice(0).forEach((fn) => fn());
		document.body.innerHTML = "";
	});

	function setup(inner) {
		const host = mountShadowPanel(inner);
		cleanups.push(isolateTyping(host));
		return host.shadowRoot;
	}

	it.each([
		["the composer textarea", "<textarea></textarea>"],
		["an input answering the assistant's question", '<input type="text">'],
		["a contenteditable", '<div contenteditable="true"></div>'],
	])("does not reach Desk's shortcuts from %s", (_, inner) => {
		const field = setup(inner).firstElementChild;
		field.focus();
		expect(document.activeElement).not.toBe(field);

		const fire = vi.fn();
		cleanups.push(deskShortcut(fire));
		press(field, { key: "?", shiftKey: true });
		press(field, { key: "T", shiftKey: true });
		expect(fire).not.toHaveBeenCalled();
	});

	it("still lets the launcher's own shortcut toggle the panel", () => {
		const field = setup("<textarea></textarea>").firstElementChild;
		const toggle = vi.fn();
		cleanups.push(bindShortcut("Ctrl+K", toggle));
		press(field, { key: "k", ctrlKey: true });
		expect(toggle).toHaveBeenCalledTimes(1);
	});

	it("leaves keys pressed outside a field to Desk", () => {
		const button = setup("<button>Send</button>").firstElementChild;
		const fire = vi.fn();
		cleanups.push(deskShortcut(fire));
		press(button, { key: "?", shiftKey: true });
		expect(fire).toHaveBeenCalledTimes(1);
	});
});
