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
 *   resolves "approve", "trust" or "deny"; anything else, or a throw, is a refusal.
 * @param {() => string|null} options.getSessionId the conversation this tab holds.
 * @param {Set<string>} [options.confirmTools] tools that need the user's approval before they run.
 * @param {(toolName: string, params: object) => string} [options.describe] a short summary for the card.
 * @param {(toolName: string, params: object) => string|null} [options.preflight] an error to answer with
 *   before asking the user, when the tool cannot run at all.
 */
export function createDispatcher({
	transport,
	handlers,
	confirm,
	getSessionId,
	confirmTools = new Set(),
	describe = () => "",
	preflight = () => null,
	retries = 3,
	retryDelayMs = 500,
}) {
	const processed = new Set();
	// "Always Allow" lasts as long as this dispatcher: a reload forgets it.
	const trusted = new Set();
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

	async function askUser(tool_name, params) {
		let decision;
		try {
			decision = await confirm({ tool_name, params, description: describe(tool_name, params) });
		} catch (e) {
			// A broken prompt must never read as consent.
			logger.warn("Confirmation failed; denying tool call by default.", e);
			return "deny";
		}
		if (decision !== "approve" && decision !== "trust") return "deny";
		if (decision === "trust") trusted.add(tool_name);
		return decision;
	}

	async function handle(data) {
		const { call_id, tool_name } = data || {};
		const params = data?.params || {};

		// Only the tab holding the conversation answers it; otherwise another tab reports its own
		// page. The task_progress room is the primary filter, this is defence in depth.
		const sid = getSessionId();
		if (data?.session_id && sid && data.session_id !== sid) return;

		if (processed.has(call_id)) return;
		processed.add(call_id);
		setTimeout(() => processed.delete(call_id), DEDUPE_WINDOW_MS);

		// Until this lands the server cannot tell "nobody is listening" from "the user is deciding".
		reportProgress(call_id, "received");

		try {
			const handler = handlers[tool_name];
			if (!handler) {
				await submit(call_id, null, `Unknown browser tool: ${tool_name}`);
				return;
			}
			const blocked = preflight(tool_name, params);
			if (blocked) {
				await submit(call_id, null, blocked);
				return;
			}
			if (confirmTools.has(tool_name) && !trusted.has(tool_name)) {
				// The server suspends its short delivery deadline while a human decides.
				reportProgress(call_id, "awaiting_user");
				if ((await askUser(tool_name, params)) === "deny") {
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

	function stop() {
		listening = false;
		if (unsubscribe) unsubscribe();
		unsubscribe = null;
	}

	return { handle, drainPending, start, stop };
}
