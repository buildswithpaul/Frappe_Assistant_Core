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

// Comparing with an empty string asks whether the field is blank, which a blank in the sentence would hide.
const BLANK_SENTENCES = {
	"==": (field) => __("when {0} is empty", [field]),
	"!=": (field) => __("when {0} is set", [field]),
};

function derive(text) {
	const comparison = COMPARISON.exec(text);
	if (comparison) {
		const [, field, operator, value] = comparison;
		const label = formatKey(field);
		if (value.length === 2 && /^['"]/.test(value)) return BLANK_SENTENCES[operator.slice(0, 2)]?.(label);
		return SENTENCES[operator](label, unquote(value));
	}
	const bare = BARE_FIELD.exec(text);
	return bare ? __("when {0} is set", [formatKey(bare[1])]) : undefined;
}

// A card must still render for any value the model wrote, so nothing here may throw.
export function describeCondition(expression) {
	try {
		return derive(typeof expression === "string" ? expression.trim() : "") ?? __("Has a condition");
	} catch {
		return __("Has a condition");
	}
}
