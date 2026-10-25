import { expect } from "vitest";

import { fireInlineHandlers } from "./inlineHandlers";

// The html a held page must not run anything from, for the chat panel's and Desk's strips alike.
export const HELD_HTML =
	'<p>Sales</p><img class="pic" src="x" onerror="window.__heldRan = 1"><svg onload="window.__heldRan = 2">' +
	'<animate attributeName="href" to="javascript:window.__heldRan = 3"></animate>' +
	'<set attributeName="href" to="javascript:window.__heldRan = 4"></set></svg>' +
	'<a class="go" href=" java\tscript:window.__heldRan = 5">go</a>' +
	'<a class="doc" href="data:text/html,<script>parent.__heldRan = 6</script>">doc</a>' +
	'<img class="data-pic" src="data:image/svg+xml,<svg onload=alert(1)>">' +
	'<iframe srcdoc="<script>parent.__heldRan = 7</script>"></iframe>' +
	'<object data="x"></object><embed src="x"><base href="https://evil.example/">' +
	'<form class="mk-form" action="javascript:window.__heldRan = 8"><input name="q">' +
	'<button type="submit" formaction="data:text/html,x">Go</button></form>' +
	'<form class="mk-local" action="/api/method/x"></form>';

/** Assert a root drawn from HELD_HTML carries nothing that runs, and keeps its forms. */
export function expectNothingRuns(root) {
	fireInlineHandlers(root, "error");
	fireInlineHandlers(root, "load");
	expect(window.__heldRan).toBeUndefined();
	for (const tag of ["iframe", "object", "embed", "base", "animate", "set", "script"]) {
		expect(root.querySelector(tag)).toBeNull();
	}
	expect(root.querySelector("[srcdoc]")).toBeNull();
	expect(root.querySelector(".go").getAttribute("href")).toBeNull();
	expect(root.querySelector(".doc").getAttribute("href")).toBeNull();
	expect(root.querySelector(".data-pic").getAttribute("src")).toBeNull();
	expect(root.querySelector("form.mk-form").getAttribute("action")).toBeNull();
	expect(root.querySelector("form.mk-form button").getAttribute("formaction")).toBeNull();
	expect(root.querySelector("form.mk-form input[name=q]")).not.toBeNull();
	expect(root.querySelector("form.mk-local").getAttribute("action")).toBe("/api/method/x");
	expect(root.querySelector("img.pic")).not.toBeNull();
}
