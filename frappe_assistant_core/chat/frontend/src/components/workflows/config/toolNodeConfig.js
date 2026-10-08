import { __ } from "@/utils/i18n";

/** The arguments box holds a JSON object; anything else is refused, never saved. */
export function parseArguments(text) {
	if (!text || !text.trim()) return { ok: true, value: {} };
	let value;
	try {
		value = JSON.parse(text);
	} catch (err) {
		return { ok: false, error: __("Not valid JSON: {0}", [err.message]) };
	}
	if (!value || typeof value !== "object" || Array.isArray(value)) {
		return {
			ok: false,
			error: __('Arguments must be a JSON object, like {"key": "value"}'),
		};
	}
	return { ok: true, value };
}

/** Argument names the picked tool declares, from its MCP input schema. */
export function argumentHints(tool) {
	const schema = tool?.inputSchema || tool?.input_schema || null;
	const properties =
		schema?.properties && typeof schema.properties === "object" ? schema.properties : {};
	return {
		names: Object.keys(properties),
		required: Array.isArray(schema?.required) ? schema.required : [],
	};
}
