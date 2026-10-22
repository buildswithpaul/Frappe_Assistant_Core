// A vendor word leading a model's display name ("Claude Sonnet 4.6") says nothing the rest of
// the name does not; a phone's toolbar shows the rest ("Sonnet 4.6").
const VENDOR_PREFIX = /^(?:Claude|Anthropic|OpenAI|Google|Meta|Mistral)\s+(?=\S)/i;

export function shortModelName(name) {
	return (name || "").trim().replace(VENDOR_PREFIX, "");
}
