import { describe, it, expect } from "vitest";
import postcss from "postcss";
import { postcssShadowHost } from "../../../build/postcssShadowHost.js";
import { findTeleportToBody, findTailwindUtilities } from "../../../build/widgetGuards.js";

const run = async (css) => (await postcss([postcssShadowHost()]).process(css, { from: undefined })).css;

describe("postcssShadowHost", () => {
	it("moves page tokens onto the host", async () => {
		expect(await run(":root{--ql-bg:#fff}")).toBe(":host{--ql-bg:#fff}");
	});

	it("retargets theme selectors quoted and unquoted — Vite strips the quotes", async () => {
		expect(await run('[data-theme="dark"]{--a:1}')).toBe(':host([data-theme="dark"]){--a:1}');
		expect(await run("[data-theme=dark] .x{--a:1}")).toBe(':host([data-theme="dark"]) .x{--a:1}');
		expect(await run('html[data-theme="dark"] .faco-widget{c:1}')).toBe(':host([data-theme="dark"]) .faco-widget{c:1}');
	});

	it("drops rules aimed at the page itself", async () => {
		expect(await run("html, body, #app{height:100%} .keep{c:1}")).toBe(".keep{c:1}");
		expect(await run("body{margin:0}")).toBe("");
	});

	it("keeps the real selectors of a list that mixes page and component selectors", async () => {
		expect(await run("html, body, .x{c:1}")).toBe(".x{c:1}");
	});

	it("leaves component selectors alone", async () => {
		expect(await run(".text-block[data-v-1] p{m:0}")).toBe(".text-block[data-v-1] p{m:0}");
	});
});

describe("widget guards", () => {
	it("finds a teleport to the page body", () => {
		expect(findTeleportToBody('<Teleport to="body"><div/></Teleport>')).toBe(true);
		expect(findTeleportToBody('<Teleport :to="teleportTarget">')).toBe(false);
	});

	it("reports Tailwind utilities except the icon sizes the widget defines", () => {
		expect(findTailwindUtilities('<svg class="w-4 h-4"/>')).toEqual([]);
		expect(findTailwindUtilities('<div class="flex items-center px-2 card">')).toEqual(["flex", "items-center", "px-2"]);
	});
});
