import { describe, it, expect } from "vitest";
import { greetingForHour, displayNameFromUser } from "../welcomeGreeting";

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

import { formatDateLabel, relativeTimeLabel } from "../welcomeGreeting";

describe("formatDateLabel", () => {
	it("renders weekday · day month", () => {
		expect(formatDateLabel(new Date(2026, 6, 6))).toBe("Monday · 6 July");
	});
});

describe("relativeTimeLabel", () => {
	const now = new Date("2026-07-06T18:00:00");
	it("minutes", () => expect(relativeTimeLabel("2026-07-06 17:48:00", now)).toBe("12m ago"));
	it("hours", () => expect(relativeTimeLabel("2026-07-06 16:00:00", now)).toBe("2h ago"));
	it("yesterday", () => expect(relativeTimeLabel("2026-07-05 20:00:00", now)).toBe("yesterday"));
	it("days", () => expect(relativeTimeLabel("2026-07-03 12:00:00", now)).toBe("3d ago"));
	it("older falls back to short date", () =>
		expect(relativeTimeLabel("2026-06-12 12:00:00", now)).toBe("12 Jun"));
	it("just now", () => expect(relativeTimeLabel("2026-07-06 17:59:40", now)).toBe("just now"));
});
