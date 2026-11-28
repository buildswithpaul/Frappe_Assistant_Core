import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRememberedTab } from "./rememberedTab";

describe("useRememberedTab", () => {
	beforeEach(() => window.localStorage.clear());
	afterEach(() => vi.restoreAllMocks());

	it("starts on the first tab and remembers the one chosen", () => {
		const first = useRememberedTab("tool", ["summary", "raw"]);
		expect(first.tab.value).toBe("summary");

		first.choose("raw");

		expect(useRememberedTab("tool", ["summary", "raw"]).tab.value).toBe("raw");
	});

	it("ignores a stored tab this kind of call no longer has", () => {
		// An earlier release of the app may have stored a tab name that has since gone.
		window.localStorage.setItem("fac-chat:tool-tab:tool", "details");

		expect(useRememberedTab("tool", ["summary", "raw"]).tab.value).toBe("summary");
	});

	it("still switches tabs when the browser blocks storage", () => {
		// A private window, or site data blocked: every storage call throws.
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
			throw new DOMException("blocked", "SecurityError");
		});
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new DOMException("blocked", "SecurityError");
		});

		const { tab, choose } = useRememberedTab("tool", ["summary", "raw"]);
		choose("raw");

		expect(tab.value).toBe("raw");
	});
});
