import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const widgetJs = resolve(process.cwd(), "../../public/chat/widget/widget.js");
const autofadeJs = resolve(process.cwd(), "../../public/chat/widget/widget_autofade.js");
const baseCss = resolve(process.cwd(), "../../public/chat/widget/widget_base.css");

describe("Desk widget on phone and tablet", () => {
	it("mounts for signed-in Desk users, including compact viewports", () => {
		const src = readFileSync(widgetJs, "utf8");
		expect(src).toMatch(/function shouldMountFACOWidget/);
		expect(src).toMatch(/frappe\.session\.user !== "Guest"/);
		expect(src).not.toMatch(/if\s*\(\s*!frappe\.is_mobile\(\)/);
		expect(src).not.toMatch(/Skipping widget: mobile=/);
	});

	it("does not fade the launcher below laptop width", () => {
		const src = readFileSync(autofadeJs, "utf8");
		expect(src).toMatch(/innerWidth < 1024/);
	});

	it("does not open the panel on Desk refresh", () => {
		const src = readFileSync(widgetJs, "utf8");
		const init = src.match(/async init\(\) \{([\s\S]*?)\n\tasync check_access/);
		expect(init).not.toBeNull();
		expect(init[1]).not.toMatch(/this\.open\(\)/);
	});

	it("anchors the open panel above the launcher on compact viewports", () => {
		const css = readFileSync(baseCss, "utf8");
		expect(css).toMatch(/@media \(max-width: 1023px\)/);
		expect(css).toMatch(/z-index:\s*10050/);
		expect(css).toMatch(/\.faco-widget\.faco-open \.faco-chat-window/);
		expect(css).toMatch(/top:\s*auto\s*!important/);
		expect(css).toMatch(/bottom:\s*76px\s*!important/);
	});
});
