import { __ } from "@/utils/i18n";

const REGION_PREFIX = /^(?:global|us|eu|apac)\./;
const PROVIDER_PREFIX = /^(?:anthropic|openai|meta|amazon|google|mistral)[./]/;
// A vendor prefix the list above does not know ("zai.glm-5"); a dot before a digit is a version.
const UNKNOWN_PROVIDER_PREFIX = /^[a-z][a-z0-9]*\.(?=[a-z])/;
const VERSION_SUFFIX = /-v\d+(?::\d+)?$/;
const DATE_SUFFIX = /-\d{8}$/;
const SINGLE_DIGIT = /^\d$/;
const PARAMETER_COUNT = /^\d+b$/i;
const ACRONYMS = { glm: "GLM" };

function titleCase(word) {
	if (ACRONYMS[word]) return ACRONYMS[word];
	if (PARAMETER_COUNT.test(word)) return word.toUpperCase();
	return word.charAt(0).toUpperCase() + word.slice(1);
}

function joinDigitRuns(tokens) {
	const joined = [];
	for (const token of tokens) {
		const last = joined.length - 1;
		if (SINGLE_DIGIT.test(token) && last >= 0 && joined[last].split(".").every((p) => SINGLE_DIGIT.test(p))) {
			joined[last] += `.${token}`;
		} else {
			joined.push(token);
		}
	}
	return joined;
}

export function formatModelId(id) {
	if (!id) return __("Unknown model");
	const stripped = id
		.toLowerCase()
		.replace(REGION_PREFIX, "")
		.replace(PROVIDER_PREFIX, "")
		.replace(UNKNOWN_PROVIDER_PREFIX, "")
		.replace(VERSION_SUFFIX, "")
		.replace(DATE_SUFFIX, "");
	const tokens = joinDigitRuns(stripped.split("-").filter(Boolean));

	const words = [];
	for (let i = 0; i < tokens.length; i++) {
		if (tokens[i] === "gpt" && /^\d/.test(tokens[i + 1] || "")) {
			words.push(`GPT-${tokens[i + 1]}`);
			i++;
		} else if (tokens[i] === "gpt") {
			words.push("GPT");
		} else {
			words.push(titleCase(tokens[i]));
		}
	}
	return words.join(" ") || __("Unknown model");
}
