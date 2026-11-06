// Frappe Assistant Core - Browser tool call dispatch
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

/**
 * The transport-agnostic half of a browser tool host: the Desk widget runs it over
 * frappe.realtime, the chat SPA over its own socket. The server side is
 * plugins/faco/tools/browser_bridge.py.
 */
import { logger } from "@/utils/logger";

const BRIDGE = "frappe_assistant_core.plugins.faco.tools.browser_bridge";

export const BROWSER_TOOL_CALL_EVENT = "faco_browser_tool_call";
export const ACK_METHOD = `${BRIDGE}.submit_browser_tool_ack`;
export const RESULT_METHOD = `${BRIDGE}.submit_browser_tool_result`;
export const PENDING_METHOD = `${BRIDGE}.get_pending_browser_tool_calls`;

export const DECLINED_ERROR = "User declined to execute this browser tool. Ask before attempting again.";

// A call can arrive twice, over the socket and from the pending queue; remember it this long.
const DEDUPE_WINDOW_MS = 60000;

/**
 * @param {object} options
 * @param {{on: (event: string, fn: Function) => (Function|void), call: (method: string, args: object) => Promise<any>}} options.transport
 *   `on` subscribes and may return an unsubscribe; `call` posts and resolves with the response's message.
 * @param {Record<string, Function>} options.handlers tool name → async handler(params); looked up per call.
 * @param {(request: {tool_name: string, params: object, description: string}) => Promise<string>} options.confirm
 *   resolves "approve", "trust", "trust_page" or "deny"; anything else, or a throw, is a refusal.
 * @param {() => string|null} options.getSessionId the conversation this tab holds.
 * @param {Set<string>} [options.confirmTools] tools that need the user's approval before they run.
 * @param {(toolName: string, params: object) => string} [options.describe] a short summary for the card.
 * @param {(toolName: string, params: object) => string|null} [options.preflight] an error to answer with
 *   before asking the user, when the tool cannot run at all.
 * @param {(call: object) => boolean} [options.ownsCall] whether this client asked for the call. The widget
 *   and the chat app can hold the same conversation and share its room; a call this client does not
 *   own is left alone, with no ack and no result, for the client that does.
 * @param {(toolName: string) => string} [options.unknownToolError] the error a call for a tool with no
 *   handler is answered with. An owned call is always answered: no other client will, and the server
 *   would hold the turn until its deadline.
 * @param {(toolName: string, params: object) => string} [options.trustKey] what "Always Allow" covers;
 *   the tool by default.
 * @param {(toolName: string, params: object) => string|null} [options.pageTrustKey] what "Allow on this
 *   page in this chat" covers. Null when there is no page or chat to key, and then that answer is a
 *   one-off approval, as it is when the key has changed by the time the user answers.
 */
export function createDispatcher({
	transport,
	handlers,
	confirm,
	getSessionId,
	confirmTools = new Set(),
	describe = () => "",
	preflight = () => null,
	ownsCall = () => true,
	unknownToolError = (toolName) => `Unknown browser tool: ${toolName}`,
	trustKey = (toolName) => toolName,
	pageTrustKey = () => null,
	retries = 3,
	retryDelayMs = 500,
}) {
	const processed = new Set();
	// "Always Allow" lasts as long as this dispatcher: a reload forgets it.
	const trusted = new Set();
	const trustedPages = new Set();
	// Settles each confirmation still open when the dispatcher stops.
	const openAsks = new Set();
	let listening = false;
	let unsubscribe = null;

	// Telemetry for the server's deadline, never a gate: it is not awaited, and a failure is dropped.
	// The server only ever extends its deadline, so reports arriving out of order are harmless.
	function reportProgress(call_id, state) {
		const failed = (error) => logger.debug(`Progress report '${state}' failed for ${call_id}:`, error);
		try {
			Promise.resolve(transport.call(ACK_METHOD, { call_id, state })).catch(failed);
		} catch (error) {
			failed(error);
		}
	}

	async function submit(call_id, result, error) {
		// Frappe's type validation rejects an empty value for a dict, so absent keys stay absent.
		const args = { call_id };
		if (result !== null && result !== undefined) args.result = result;
		if (error !== null && error !== undefined) args.error = error;
		for (let attempt = 1; attempt <= retries; attempt++) {
			try {
				await transport.call(RESULT_METHOD, args);
				return;
			} catch (e) {
				logger.error(`Submitting browser tool result ${call_id} failed (${attempt}/${retries}):`, e);
				if (attempt < retries) await new Promise((r) => setTimeout(r, retryDelayMs * attempt));
			}
		}
	}

	async function askUser(tool_name, params, key, pageKey) {
		let decision;
		let settleOnStop;
		const stopped = new Promise((resolve) => (settleOnStop = () => resolve("deny")));
		openAsks.add(settleOnStop);
		try {
			const asked = confirm({ tool_name, params, description: describe(tool_name, params) });
			decision = await Promise.race([asked, stopped]);
		} catch (e) {
			// A broken prompt must never read as consent.
			logger.warn("Confirmation failed; denying tool call by default.", e);
			return "deny";
		} finally {
			openAsks.delete(settleOnStop);
		}
		if (!["approve", "trust", "trust_page"].includes(decision)) return "deny";
		if (decision === "trust") trusted.add(key);
		// Another page or chat by now: the user answered about the one the card showed.
		else if (decision === "trust_page" && pageKey && pageKey === pageTrustKey(tool_name, params)) {
			trustedPages.add(pageKey);
		}
		return decision;
	}

	async function handle(data) {
		const { call_id, tool_name } = data || {};
		const params = data?.params || {};

		// Only the tab holding the conversation answers it; otherwise another tab reports its own
		// page. The task_progress room is the primary filter, this is defence in depth.
		const sid = getSessionId();
		if (data?.session_id && sid && data.session_id !== sid) return;
		if (!ownsCall(data)) return;

		if (processed.has(call_id)) return;
		processed.add(call_id);
		setTimeout(() => processed.delete(call_id), DEDUPE_WINDOW_MS);

		// Until this lands the server cannot tell "nobody is listening" from "the user is deciding".
		reportProgress(call_id, "received");

		try {
			const handler = handlers[tool_name];
			if (!handler) {
				await submit(call_id, null, unknownToolError(tool_name));
				return;
			}
			const blocked = preflight(tool_name, params);
			if (blocked) {
				await submit(call_id, null, blocked);
				return;
			}
			const key = trustKey(tool_name, params);
			const pageKey = pageTrustKey(tool_name, params);
			const isTrusted = trusted.has(key) || Boolean(pageKey && trustedPages.has(pageKey));
			if (confirmTools.has(tool_name) && !isTrusted) {
				// The server suspends its short delivery deadline while a human decides.
				reportProgress(call_id, "awaiting_user");
				if ((await askUser(tool_name, params, key, pageKey)) === "deny") {
					await submit(call_id, null, DECLINED_ERROR);
					return;
				}
			}
			reportProgress(call_id, "executing");
			const result = await handler.call(handlers, params);
			if (result && result.error) await submit(call_id, null, result.error);
			else await submit(call_id, result, null);
		} catch (error) {
			logger.error("Browser tool execution failed:", error);
			await submit(call_id, null, error.message);
		}
	}

	/** Answer calls that arrived before this host listened, e.g. across a page load. */
	async function drainPending() {
		try {
			const calls = (await transport.call(PENDING_METHOD, { session_id: getSessionId() || null })) || [];
			for (const call of calls) await handle(call);
		} catch (e) {
			// Not critical: the server times such calls out.
			logger.warn("Failed to fetch pending browser tool calls:", e);
		}
	}

	function start() {
		if (listening) return;
		listening = true;
		const off = transport.on(BROWSER_TOOL_CALL_EVENT, (data) => (listening ? handle(data) : undefined));
		unsubscribe = typeof off === "function" ? off : null;
	}

	/** Stop listening, and deny any confirmation still open: nobody is left to answer it. */
	function stop() {
		openAsks.forEach((settle) => settle());
		listening = false;
		if (unsubscribe) unsubscribe();
		unsubscribe = null;
	}

	return { handle, drainPending, start, stop };
}
