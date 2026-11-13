import { __ } from "@/utils/i18n";
import { featureById } from "./featureCatalog";

/**
 * The Did you know tips. They ship with FAC, one set per release, so each tip only talks about
 * features this version has. FAC Chat shows one a day and cycles through them in this order,
 * skipping a feature the user already uses and a tip they asked never to see again.
 *
 * Keep an id once it has shipped: "Don't show this tip again" is stored by id.
 * A tip with no route uses its feature's own Try (the template browser, the Pages prompt).
 */
const TIPS = [
	{
		id: "ask-in-plain-words",
		feature: "ask",
		message: () =>
			__("Ask about your business in plain words. FAC reads your ERPNext data and answers, with your own permissions."),
		highlights: () => [__("Ask a follow-up to dig deeper")],
		actionLabel: () => __("Try a question"),
		route: () => `/chat?prompt=${encodeURIComponent(__("Who owes us the most, and since when?"))}`,
	},
	{
		id: "agents-routine-work",
		feature: "agents",
		message: () => __("An agent can email you overdue invoices every Monday, and do other routine work on a schedule."),
		highlights: () => [__("Start from a ready-made template")],
		actionLabel: () => __("Show me agents"),
		route: () => "/agents?tab=marketplace",
	},
	{
		id: "templates-ask-again",
		feature: "templates",
		message: () => __("Ask the same question every week? Save it as a prompt template and run it again in one click."),
		highlights: () => [],
		actionLabel: () => __("Show me templates"),
		route: () => null,
	},
	{
		id: "knowledge-your-files",
		feature: "knowledge",
		message: () => __("Upload a price list, a policy or a manual to Knowledge, and FAC answers from it."),
		highlights: () => [],
		actionLabel: () => __("Open Knowledge"),
		route: () => "/knowledge",
	},
	{
		id: "pages-keep-an-answer",
		feature: "pages",
		message: () => __("Keep any answer as a Page: a live report you can open again whenever you need it."),
		highlights: () => [],
		actionLabel: () => __("Show me Pages"),
		route: () => null,
	},
];

/** The ids in the order tips take turns. */
export const TIP_ORDER = TIPS.map((t) => t.id);

/**
 * This site's tips, translated, in the shape the tip line and its pop-up read. A tip about a
 * feature the site has switched off (Knowledge, Agents) is left out.
 */
export function dailyTips(flags = {}) {
	return TIPS.filter((t) => {
		const capability = featureById(t.feature)?.capability;
		return !capability || flags[capability] === true;
	}).map((t) => ({
		id: t.id,
		feature: t.feature,
		title: __("Did you know?"),
		message: t.message(),
		highlights: t.highlights(),
		action_label: t.actionLabel(),
		action_route: t.route(),
		dismissible: true,
	}));
}
