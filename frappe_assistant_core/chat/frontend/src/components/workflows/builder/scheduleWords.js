import { __ } from "@/utils/i18n";

/** Schedules a person can pick without writing cron; anything else stays "custom". */
export const FREQUENCIES = ["hourly", "daily", "weekdays", "weekly", "monthly"];

export const WEEKDAYS = () => [
	__("Sunday"),
	__("Monday"),
	__("Tuesday"),
	__("Wednesday"),
	__("Thursday"),
	__("Friday"),
	__("Saturday"),
];

const int = (field, min, max) => {
	if (!/^\d{1,2}$/.test(field)) return null;
	const n = Number(field);
	return n >= min && n <= max ? n : null;
};

/** The simple-picker reading of a cron expression, or null when it needs Advanced. */
export function parseCron(cron) {
	const parts = (cron || "").trim().split(/\s+/);
	if (parts.length !== 5) return null;
	const [min, hr, dom, mon, dow] = parts;
	const minute = int(min, 0, 59);
	if (minute === null || mon !== "*") return null;

	if (hr === "*" && dom === "*" && dow === "*") return { freq: "hourly", minute };
	const hour = int(hr, 0, 23);
	if (hour === null) return null;

	if (dom === "*" && dow === "*") return { freq: "daily", hour, minute };
	if (dom === "*" && dow === "1-5") return { freq: "weekdays", hour, minute };
	if (dom === "*") {
		const weekday = int(dow, 0, 6);
		return weekday === null ? null : { freq: "weekly", hour, minute, weekday };
	}
	const monthday = int(dom, 1, 31);
	if (monthday === null || dow !== "*") return null;
	return { freq: "monthly", hour, minute, monthday };
}

export function toCron({ freq, hour = 9, minute = 0, weekday = 1, monthday = 1 }) {
	return {
		hourly: `${minute} * * * *`,
		daily: `${minute} ${hour} * * *`,
		weekdays: `${minute} ${hour} * * 1-5`,
		weekly: `${minute} ${hour} * * ${weekday}`,
		monthly: `${minute} ${hour} ${monthday} * *`,
	}[freq];
}

const pad = (n) => String(n).padStart(2, "0");

export function describeSchedule(cron, timezone) {
	if (!cron) return "";
	const zone = timezone || "UTC";
	const s = parseCron(cron);
	if (!s) return __("Custom schedule: {0} ({1})", [cron, zone]);
	const time = `${pad(s.hour)}:${pad(s.minute)}`;
	const words = {
		hourly: () => __("Every hour at :{0}", [pad(s.minute)]),
		daily: () => __("Every day at {0}", [time]),
		weekdays: () => __("Weekdays at {0}", [time]),
		weekly: () => __("Every {0} at {1}", [WEEKDAYS()[s.weekday], time]),
		monthly: () => __("Day {0} of every month at {1}", [s.monthday, time]),
	}[s.freq]();
	return `${words} (${zone})`;
}

/**
 * Imports arrive switched off and in UTC, a zone nobody chose; propose the
 * browser's instead. A zone someone picked, or a live schedule, is kept.
 */
export function proposedTimezone(schedule, browserZone) {
	const zone = schedule?.timezone || "UTC";
	if (zone === "UTC" && !schedule?.enabled && browserZone) return browserZone;
	return zone;
}
