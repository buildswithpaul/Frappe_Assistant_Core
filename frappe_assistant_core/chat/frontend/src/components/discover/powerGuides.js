import { __ } from "@/utils/i18n";

/**
 * Your FAC: the one line a first-timer sees on a power's own page, saying what to do there to try it.
 * Shown until the power is used or the user closes it. Pages has its own explain card instead.
 * A guide with a `route` shows on that page; templates shows when Try opens the template list.
 */
export const GUIDES = {
	knowledge: {
		route: "/knowledge",
		text: () =>
			__("Files you see here may be shared by your team. Upload your own file, then ask FAC about it, to try Knowledge."),
	},
	agents: {
		route: "/agents",
		text: () => __("Pick a ready-made template here and create your own agent to try Agents."),
	},
	templates: {
		route: null,
		text: () => __("Pick a template: FAC puts its question in the ask box for you to send. That tries Prompt templates."),
	},
};

/** The guide for a page the user is on, or null. */
export function guideForPath(path) {
	const hit = Object.entries(GUIDES).find(([, g]) => g.route && (path === g.route || path.startsWith(`${g.route}/`)));
	return hit ? hit[0] : null;
}
