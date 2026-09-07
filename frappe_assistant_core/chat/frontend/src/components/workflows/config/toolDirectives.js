/**
 * Pure helpers behind the agent node's tool configurator.
 *
 * The engine resolves a directive by matching `tool_name` against the MCP
 * tool's BARE name (`original_name`). The tools API also returns a
 * server-prefixed `name` ("Main Frappe Site:list_documents") — writing that
 * form into `tool_name` is what made every picked tool resolve as "missing".
 */

/** The name the engine matches on. */
export function bareToolName(tool) {
	return tool?.original_name || tool?.name || "";
}

/** Strip a "server:" prefix from a directive name saved by an older builder. */
export function healToolName(toolName) {
	if (!toolName || typeof toolName !== "string") return "";
	const i = toolName.indexOf(":");
	return i === -1 ? toolName : toolName.slice(i + 1);
}

/** Build the directive the engine expects from a tool the picker offered. */
export function makeDirective(tool) {
	const bare = bareToolName(tool);
	return {
		capability: bare,
		tool_name: bare,
		description: tool?.description || "",
		required: false,
		priority: "primary",
	};
}

/**
 * Heal directives saved with a prefixed tool_name, and drop `input_guidance`
 * (written by every past builder version, read by nothing).
 *
 * Returns { directives, changed } so the caller can persist only a real change.
 */
export function normalizeDirectives(directives = []) {
	let changed = false;
	const normalized = directives.map((d) => {
		const healed = healToolName(d.tool_name);
		const next = { ...d, tool_name: healed };
		if (healed !== d.tool_name) changed = true;
		if (!next.capability) next.capability = healed;
		if ("input_guidance" in next) {
			delete next.input_guidance;
			changed = true;
		}
		return next;
	});
	return { directives: normalized, changed };
}

/** Which MCP server serves this directive, as far as the client can tell. */
export function serverForDirective(directive, allTools = []) {
	const name = directive?.tool_name || "";
	const match = allTools.find((t) => bareToolName(t) === name || t.name === name);
	if (match?.server) return match.server;
	const i = name.indexOf(":");
	return i === -1 ? "" : name.slice(0, i);
}

/**
 * Server scoping for the node, derived additively from the directives.
 *
 * Returns `null` when nothing can be derived and no tool inventory is loaded —
 * the caller must then leave `mcp_servers` untouched. Writing `[]` reads to the
 * engine as "no filtering", silently widening the node to every server the
 * runtime user owns.
 */
export function deriveMCPServers(directives = [], allTools = [], currentServers = []) {
	const servers = new Set((currentServers || []).filter(Boolean));
	let derivedAny = false;

	for (const directive of directives) {
		const server = serverForDirective(directive, allTools);
		if (server) {
			servers.add(server);
			derivedAny = true;
		}
	}

	if (!derivedAny && !allTools.length) return null;
	return [...servers];
}

/** Index a resolve_workflow_tools response by the directive name it answers. */
export function resolutionIndex(resolved = []) {
	const index = new Map();
	for (const entry of resolved) {
		if (entry?.tool_name) index.set(healToolName(entry.tool_name), entry);
	}
	return index;
}

/**
 * Classify what the tool-discovery call actually told us.
 *
 * `list_user_tools` answers {success, tools, servers_queried, errors} and
 * returns success with an empty list for several very different situations.
 * Rendering "No tools found" for all of them is why an expired token looks
 * like an empty toolbox.
 *
 * @returns {"ok"|"loading"|"failed"|"auth"|"no-servers"|"empty"}
 */
export function toolDiscoveryState({ result, isLoading = false } = {}) {
	if (isLoading) return "loading";
	if (!result) return "failed";
	if (result.success === false) return "failed";

	const errors = Array.isArray(result.errors) ? result.errors : [];
	if (errors.length) {
		const needsAuth = errors.some((e) => AUTH_ERROR_CODES.has(e?.error_code));
		return needsAuth ? "auth" : "failed";
	}

	const tools = Array.isArray(result.tools) ? result.tools : [];
	if (tools.length) return "ok";

	const queried = Array.isArray(result.servers_queried) ? result.servers_queried : [];
	return queried.length ? "empty" : "no-servers";
}

const AUTH_ERROR_CODES = new Set([
	"NO_REFRESH_TOKEN",
	"REFRESH_TOKEN_EXPIRED",
	"MISSING_CLIENT_CREDENTIALS",
	"AUTH_FAILED",
]);

/** Server names whose failure was an authentication problem. */
export function serversNeedingReconnect(result) {
	const errors = Array.isArray(result?.errors) ? result.errors : [];
	return errors.filter((e) => AUTH_ERROR_CODES.has(e?.error_code)).map((e) => e.server);
}
