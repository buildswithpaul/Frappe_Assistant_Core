/**
 * Plain-language reading of a field's depends_on / mandatory_depends_on / read_only_depends_on value.
 *
 * Only the simple shapes are read; anything else is "Has a condition" rather than a guess, and the
 * card keeps the raw expression behind "Show technical details".
 */

import { __ } from "@/utils/i18n";
import { formatKey } from "./helpers";

const CONDITION_KEYS = ["depends_on", "mandatory_depends_on", "read_only_depends_on"];

export const isConditionKey = (key) => CONDITION_KEYS.includes(key);

const COMPARISON = /^eval:\s*doc\.(\w+)\s*(>=|<=|===|!==|==|!=|>|<)\s*(-?\d+(?:\.\d+)?|'[^']*'|"[^"]*")\s*$/;
const BARE_FIELD = /^eval:\s*doc\.(\w+)\s*$/;

const SENTENCES = {
	">": (field, value) => __("when {0} is over {1}", [field, value]),
	">=": (field, value) => __("when {0} is at least {1}", [field, value]),
	"<": (field, value) => __("when {0} is under {1}", [field, value]),
	"<=": (field, value) => __("when {0} is at most {1}", [field, value]),
	"==": (field, value) => __("when {0} is {1}", [field, value]),
	"!=": (field, value) => __("when {0} is not {1}", [field, value]),
};
SENTENCES["==="] = SENTENCES["=="];
SENTENCES["!=="] = SENTENCES["!="];

const unquote = (value) => (/^['"]/.test(value) ? value.slice(1, -1) : value);

export function describeCondition(expression) {
	const text = typeof expression === "string" ? expression.trim() : "";
	const comparison = COMPARISON.exec(text);
	if (comparison) {
		const [, field, operator, value] = comparison;
		return SENTENCES[operator](formatKey(field), unquote(value));
	}
	const bare = BARE_FIELD.exec(text);
	if (bare) return __("when {0} is set", [formatKey(bare[1])]);
	return __("Has a condition");
}
