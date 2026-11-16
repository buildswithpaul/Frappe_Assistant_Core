import { afterEach, describe, expect, it, vi } from "vitest";

import { deskTheme, followDeskTheme, mirrorDeskTheme } from "./deskTheme";

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => document.documentElement.removeAttribute("data-theme"));

describe("Desk's theme", () => {
	it("reads html[data-theme], and anything but dark is light", () => {
		document.documentElement.setAttribute("data-theme", "dark");
		expect(deskTheme()).toBe("dark");
		document.documentElement.setAttribute("data-theme", "automatic");
		expect(deskTheme()).toBe("light");
		document.documentElement.removeAttribute("data-theme");
		expect(deskTheme()).toBe("light");
	});

	it("tells a listener when the theme changes, and stops when asked", async () => {
		document.documentElement.setAttribute("data-theme", "light");
		const onChange = vi.fn();
		const stop = followDeskTheme(onChange);
		document.documentElement.setAttribute("data-theme", "dark");
		await tick();
		expect(onChange).toHaveBeenLastCalledWith("dark");
		stop();
		document.documentElement.setAttribute("data-theme", "light");
		await tick();
		expect(onChange).toHaveBeenCalledTimes(1);
	});

	it("copies Desk's theme onto a host now and follows a later change", async () => {
		document.documentElement.setAttribute("data-theme", "light");
		const host = document.createElement("div");
		const stop = mirrorDeskTheme(host);
		expect(host.getAttribute("data-theme")).toBe("light");
		document.documentElement.setAttribute("data-theme", "dark");
		await tick();
		expect(host.getAttribute("data-theme")).toBe("dark");
		stop();
	});
});
