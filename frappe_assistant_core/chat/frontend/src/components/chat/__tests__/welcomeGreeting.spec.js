import { describe, it, expect, vi, afterEach } from "vitest";
import { greetingForHour, greetingLineForHour, displayNameFromUser } from "../welcomeGreeting";

describe("greetingForHour", () => {
	it("morning between 5 and 11", () => {
		expect(greetingForHour(5)).toBe("Good morning");
		expect(greetingForHour(11)).toBe("Good morning");
	});
	it("afternoon between 12 and 16", () => {
		expect(greetingForHour(12)).toBe("Good afternoon");
		expect(greetingForHour(16)).toBe("Good afternoon");
	});
	it("evening at 17+ and before 5", () => {
		expect(greetingForHour(17)).toBe("Good evening");
		expect(greetingForHour(23)).toBe("Good evening");
		expect(greetingForHour(2)).toBe("Good evening");
	});
	it("defaults to afternoon on bad input", () => {
		expect(greetingForHour(undefined)).toBe("Good afternoon");
	});
});

describe("greetingLineForHour", () => {
	it("returns the whole headline for the time of day", () => {
		expect(greetingLineForHour(8, "Jane")).toBe("Good morning, Jane.");
		expect(greetingLineForHour(13, "Jane")).toBe("Good afternoon, Jane.");
		expect(greetingLineForHour(20, "Jane")).toBe("Good evening, Jane.");
	});
});

describe("displayNameFromUser", () => {
	it("capitalizes the first segment of the local part", () => {
		expect(displayNameFromUser("jypaulclinton@gmail.com")).toBe("Jypaulclinton");
		expect(displayNameFromUser("paul.clinton@x.com")).toBe("Paul");
		expect(displayNameFromUser("jane_doe")).toBe("Jane");
	});
	it("falls back to 'there' for guest/empty", () => {
		expect(displayNameFromUser("Guest")).toBe("there");
		expect(displayNameFromUser(null)).toBe("there");
	});
});

import { formatDateLabel, relativeTimeLabel, uiLocale } from "../welcomeGreeting";

describe("formatDateLabel", () => {
	it("puts the day before the month in en-GB", () => {
		expect(formatDateLabel(new Date(2026, 6, 6), "en-GB")).toBe("Monday · 6 July");
	});
	it("puts the month before the day in en-US", () => {
		expect(formatDateLabel(new Date(2026, 6, 6), "en-US")).toBe("Monday · July 6");
	});
});

describe("relativeTimeLabel", () => {
	const now = new Date("2026-07-06T18:00:00");
	it("minutes", () => expect(relativeTimeLabel("2026-07-06 17:48:00", now)).toBe("12m ago"));
	it("hours", () => expect(relativeTimeLabel("2026-07-06 16:00:00", now)).toBe("2h ago"));
	it("yesterday", () => expect(relativeTimeLabel("2026-07-05 20:00:00", now)).toBe("yesterday"));
	it("days", () => expect(relativeTimeLabel("2026-07-03 12:00:00", now)).toBe("3d ago"));
	it("older falls back to a short date in the locale's order", () => {
		expect(relativeTimeLabel("2026-06-12 12:00:00", now, "en-GB")).toBe("12 Jun");
		expect(relativeTimeLabel("2026-06-12 12:00:00", now, "en-US")).toBe("Jun 12");
	});
	it("just now", () => expect(relativeTimeLabel("2026-07-06 17:59:40", now)).toBe("just now"));
});

describe("relativeTimeLabel translation", () => {
	const now = new Date(2026, 6, 6, 18, 0, 0);
	afterEach(() => vi.doUnmock("@/utils/i18n"));

	it("builds every branch through __ with whole-string placeholders", async () => {
		vi.resetModules();
		const calls = [];
		vi.doMock("@/utils/i18n", () => ({
			__: (text, args) => {
				calls.push([text, args]);
				return `T(${text})`;
			},
		}));
		const { relativeTimeLabel: label } = await import("../welcomeGreeting");

		expect(label("2026-07-06 17:59:40", now)).toBe("T(just now)");
		expect(label("2026-07-06 17:48:00", now)).toBe("T({0}m ago)");
		expect(label("2026-07-06 16:00:00", now)).toBe("T({0}h ago)");
		expect(label("2026-07-05 20:00:00", now)).toBe("T(yesterday)");
		expect(label("2026-07-03 12:00:00", now)).toBe("T({0}d ago)");
		// Older dates are a locale-formatted day and month, not translated copy.
		expect(label("2026-06-12 12:00:00", now, "en-GB")).toBe("12 Jun");
		expect(calls.filter(([, args]) => args).map(([, args]) => args[0])).toEqual([12, 2, 3]);
	});
});

describe("uiLocale", () => {
	const setBrowser = (language) => vi.spyOn(navigator, "language", "get").mockReturnValue(language);
	afterEach(() => {
		vi.restoreAllMocks();
		delete window.frappe;
		delete window.lang;
	});

	it("reads window.lang when the SPA has no Frappe boot", () => {
		setBrowser("en-US");
		window.lang = "pt-BR";
		expect(window.frappe).toBeUndefined();
		expect(uiLocale()).toBe("pt-BR");
	});

	it("prefers the Desk boot language", () => {
		setBrowser("en-US");
		window.frappe = { boot: { lang: "en-GB" } };
		expect(uiLocale()).toBe("en-GB");
	});

	it("refines a bare language with the browser's region", () => {
		setBrowser("en-IN");
		window.lang = "en";
		expect(uiLocale()).toBe("en-IN");
	});

	it("keeps the Frappe language when the browser is another language", () => {
		setBrowser("en-US");
		window.lang = "de";
		expect(uiLocale()).toBe("de");
	});

	it("uses the browser without a Frappe language, and undefined for a bad tag", () => {
		setBrowser("fr-CA");
		expect(uiLocale()).toBe("fr-CA");
		setBrowser("not a tag!");
		expect(uiLocale()).toBeUndefined();
	});
});
