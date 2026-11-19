import { describe, it, expect } from "vitest";
import { parseCron, toCron, describeSchedule, proposedTimezone } from "./scheduleWords";

describe("parseCron", () => {
	it.each([
		["15 * * * *", { freq: "hourly", minute: 15 }],
		["0 9 * * *", { freq: "daily", hour: 9, minute: 0 }],
		["30 8 * * 1-5", { freq: "weekdays", hour: 8, minute: 30 }],
		["0 9 * * 1", { freq: "weekly", hour: 9, minute: 0, weekday: 1 }],
		["0 7 1 * *", { freq: "monthly", hour: 7, minute: 0, monthday: 1 }],
	])("reads %s", (cron, expected) => {
		expect(parseCron(cron)).toMatchObject(expected);
	});

	it.each(["*/30 * * * *", "0 9 31 * *", "0 9,17 * * *", "0 9 * 1 *", "0 9 * * 1,3", "", "bad", "0 25 * * *"])(
		"returns null for %s, which the simple picker cannot express",
		(cron) => {
			expect(parseCron(cron)).toBeNull();
		}
	);
});

describe("toCron", () => {
	it("round-trips every simple shape", () => {
		for (const cron of ["15 * * * *", "0 9 * * *", "30 8 * * 1-5", "0 9 * * 1", "0 7 1 * *"]) {
			expect(toCron(parseCron(cron))).toBe(cron);
		}
	});
});

describe("describeSchedule", () => {
	it("says a template's Monday schedule in words, with its zone", () => {
		expect(describeSchedule("0 9 * * 1", "Asia/Kolkata")).toBe("Every Monday at 09:00 (Asia/Kolkata)");
	});

	it("words the other shapes", () => {
		expect(describeSchedule("15 * * * *", "UTC")).toBe("Every hour at :15 (UTC)");
		expect(describeSchedule("0 9 * * *", "UTC")).toBe("Every day at 09:00 (UTC)");
		expect(describeSchedule("30 8 * * 1-5", "UTC")).toBe("Weekdays at 08:30 (UTC)");
		expect(describeSchedule("0 7 1 * *", "UTC")).toBe("Day 1 of every month at 07:00 (UTC)");
	});

	it("labels anything else as custom and keeps the expression", () => {
		expect(describeSchedule("*/30 * * * *", "UTC")).toBe("Custom schedule: */30 * * * * (UTC)");
	});

	it("is empty with no schedule", () => {
		expect(describeSchedule("", "UTC")).toBe("");
	});
});

describe("proposedTimezone", () => {
	it("proposes the browser zone for an imported schedule that is off and in UTC", () => {
		expect(proposedTimezone({ timezone: "UTC", enabled: false }, "Asia/Kolkata")).toBe("Asia/Kolkata");
		expect(proposedTimezone({ enabled: false }, "Asia/Kolkata")).toBe("Asia/Kolkata");
	});

	it("uses the current name for a zone the browser reports by its old one", () => {
		expect(proposedTimezone({ timezone: "UTC", enabled: false }, "Asia/Calcutta")).toBe("Asia/Kolkata");
	});

	it("keeps a zone someone chose, and a live UTC schedule", () => {
		expect(proposedTimezone({ timezone: "Europe/Paris", enabled: false }, "Asia/Kolkata")).toBe("Europe/Paris");
		expect(proposedTimezone({ timezone: "UTC", enabled: true }, "Asia/Kolkata")).toBe("UTC");
	});
});
