import { describe, it, expect, afterEach } from "vitest";
import { __ } from "@/utils/i18n";

describe("__", () => {
	afterEach(() => {
		delete window.__;
	});

	it("returns the source string when no translator is loaded", () => {
		expect(__("Run")).toBe("Run");
	});

	it("fills positional arguments", () => {
		expect(__("{0} of {1} tools", [2, 5])).toBe("2 of 5 tools");
	});

	it("leaves a placeholder with no argument visible", () => {
		expect(__("Hello {0} and {1}", ["A"])).toBe("Hello A and {1}");
	});

	it("delegates to Frappe's translator when the page has one", () => {
		window.__ = (s, args) => `T:${s}:${(args || []).join(",")}`;
		expect(__("Run {0}", ["now"])).toBe("T:Run {0}:now");
	});
});
