// Frappe Assistant Copilot - Browser Tools Handler
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
 * Browser Tools Handler for FACO Widget
 *
 * This module handles browser tool calls from the AI assistant.
 * Tools are executed in the browser and results are sent back to the server.
 *
 * Available tools:
 * - get_page_context: Get structured data about the current page
 * - get_form_data: Get form field values
 * - navigate_to: Navigate to a URL
 * - take_screenshot: Capture a screenshot
 * - wait_for_page: Wait for page to finish loading
 */
import { logger } from "@/utils/logger";
import pageContext from "./pageContext.js";

const loadHtml2canvas = () => import("html2canvas-pro").then((m) => m.default || m);

// Replaced by startBrowserTools(); the default denies so an unwired host fails closed.
// getWidgetSettings fails closed (DOM extraction off) until the launcher supplies the
// real operator settings; pageContext treats only `enable_dom_extraction === false` as off.
let deps = {
	getSessionId: () => null,
	confirm: async () => "deny",
	getWidgetSettings: () => ({ privacy: { enable_dom_extraction: false } }),
};

// ---------------------------------------------------------------------------
// Browser-tool HITL confirmation (FACO-H5 remediation)
// ---------------------------------------------------------------------------
//
// Background: the audit (2026-04-21 §2 FACO-H5) flagged `take_screenshot`
// and `get_form_data` as silent exfiltration vectors — a prompt-injected
// LLM can read form PII or capture the visible record without any user
// signal.
//
// The widget already has a HITL path for server-initiated approvals:
// `widget_streaming.js::show_interaction_card` handles `approval_required`
// events emitted by the Strands `ApprovalHook` and renders a
// `.faco-interaction-card.faco-interaction-approval`. Browser tools can't
// go through that path because execution happens client-side and the
// server never sees the tool call until the result is submitted — the AR
// side literally cannot know what's on the user's screen to judge
// sensitivity. So we intercept at the browser-tool boundary, but we
// render the **same** `.faco-interaction-card` markup so users see one
// consistent approval UI across both flows.
//
// Design:
//   - Only the "read-appearing" risky tools are gated. Low-risk reads
//     (`get_page_context`, `wait_for_page`) and already-hardened writes
//     (`navigate_to`, origin-checked in FACO-H2) pass through untouched.
//   - The card reuses the existing faco-interaction-card / approval CSS
//     classes and the Reject / Approve / Always Allow button triplet so
//     the widget's two approval flows look identical.
//   - `Always Allow` is session-only (in-memory Set). No persistence —
//     a single bad click should not grant forever.
//   - If the widget is closed when a risky call arrives, we pop it open
//     so the user sees the prompt.
//   - On Reject we submit an error result so the model learns from the
//     refusal rather than waiting for a server-side timeout.

const TOOLS_REQUIRING_CONFIRMATION = new Set([
	"take_screenshot",
	"get_form_data",
	"capture_diagnostics",
]);

// Capture bounds. html2canvas' own defaults are tuned for "render this small
// widget", not "rasterize a Desk list view", and left alone they routinely take
// longer than the server is willing to wait.
const MAX_SCREENSHOT_SCALE = 1.5;
const MAX_SCREENSHOT_HEIGHT_PX = 8000;
const SCREENSHOT_IMAGE_TIMEOUT_MS = 3000;
const SCREENSHOT_OVERLAY_ID = "fac-screenshot-overlay";
// Keep the widget out of its own screenshot; .faco-widget is the legacy jQuery host.
const SCREENSHOT_HIDDEN_SELECTORS = [
	"#fac-widget-launcher",
	"#fac-widget-panel",
	`#${SCREENSHOT_OVERLAY_ID}`,
	".faco-widget",
];

export const TOOL_CONFIRMATION_COPY = {
	take_screenshot: {
		action: "Capture screenshot",
		detail: "The AI wants to capture what you're looking at and send it to the assistant. The screenshot may contain any PII visible on screen.",
	},
	get_form_data: {
		action: "Read form data",
		detail: "The AI wants to read every field on the open record (including child tables) and send it to the assistant.",
	},
	capture_diagnostics: {
		action: "Collect page diagnostics",
		detail: "The AI wants to collect this page's recent console errors, failed network requests and a screenshot, and send them to the assistant. These may contain any PII visible on screen or named in an error.",
	},
};

const FACOBrowserTools = {
	/**
	 * Tools the current widget session has trusted. Cleared on reload.
	 */
	_trustedThisSession: new Set(),

	/**
	 * Tool handlers - each handler receives params and returns a result
	 */
	handlers: {
		/**
		 * Get structured page context (always includes DOM content)
		 */
		async get_page_context() {
			const context = pageContext.detect_context();
			const result = {
				page_type: context.type,
				url: context.url,
				route: window.frappe.get_route(),
				...context,
			};

			// Honour the operator's privacy toggle (privacy.enable_dom_extraction),
			// supplied by the host via startBrowserTools; the default denies.
			const settings = deps.getWidgetSettings() || {};
			const dom_content = await pageContext.extract_screen_content(context, settings);
			result.dom_content = dom_content;

			return result;
		},

		/**
		 * Get form data from current page
		 */
		async get_form_data(params) {
			const frm = pageContext.get_current_form();
			if (!frm) {
				return {
					error: "No form is currently open. Use browser_get_page_context for non-form pages.",
				};
			}

			const doc = frm.doc;
			const meta = frm.meta;

			const result = {
				doctype: frm.doctype,
				name: doc.name,
				is_new: frm.is_new(),
				is_dirty: frm.is_dirty(),
				docstatus: doc.docstatus,
				fields: {},
			};

			// Determine which fields to include
			const requestedFields = params.fields;

			meta.fields.forEach((field) => {
				// Skip layout fields
				if (["Section Break", "Column Break", "Tab Break"].includes(field.fieldtype)) {
					return;
				}

				// If specific fields requested, only include those
				if (requestedFields && !requestedFields.includes(field.fieldname)) {
					return;
				}

				const value = doc[field.fieldname];

				// Handle child tables
				if (field.fieldtype === "Table" && params.include_child_tables !== false) {
					const tableData = doc[field.fieldname] || [];
					result.fields[field.fieldname] = {
						label: field.label,
						type: "Table",
						row_count: tableData.length,
						rows: tableData.slice(0, 20).map((row) => {
							const rowData = {};
							// Get child table meta
							const childMeta = window.frappe.get_meta(field.options);
							if (childMeta) {
								childMeta.fields.forEach((childField) => {
									if (
										!["Section Break", "Column Break"].includes(
											childField.fieldtype
										)
									) {
										const childValue = row[childField.fieldname];
										if (
											childValue !== null &&
											childValue !== undefined &&
											childValue !== ""
										) {
											rowData[childField.fieldname] = childValue;
										}
									}
								});
							}
							return rowData;
						}),
					};
				} else if (value !== null && value !== undefined && value !== "") {
					result.fields[field.fieldname] = {
						label: field.label,
						type: field.fieldtype,
						value: value,
					};
				}
			});

			return result;
		},

		/**
		 * Navigate to a URL
		 *
		 * IMPORTANT: Navigation destroys the current JS context, so we cannot
		 * wait for page load and return context. We return immediately after
		 * initiating navigation. The LLM can use browser_get_page_context or
		 * browser_wait_for_page as follow-up tools if needed.
		 */
		async navigate_to(params) {
			const url = params.url;
			if (!url) {
				return { error: "URL is required" };
			}

			// Security: Only allow same-origin navigation
			const currentOrigin = window.location.origin;
			let targetUrl = url;

			// Handle relative URLs
			if (url.startsWith("/")) {
				targetUrl = url;
			} else if (
				url.startsWith("app/") ||
				url.startsWith("Form/") ||
				url.startsWith("List/")
			) {
				targetUrl = "/" + url;
			} else if (!url.startsWith("http")) {
				// Assume it's a Frappe route like "Sales Invoice/SINV-00001"
				targetUrl = "/app/" + url.toLowerCase().replace(/ /g, "-");
			} else {
				// Full URL - verify same origin
				try {
					const urlObj = new URL(url);
					if (urlObj.origin !== currentOrigin) {
						return { error: "Cross-origin navigation is not allowed" };
					}
					targetUrl = urlObj.pathname + urlObj.search + urlObj.hash;
				} catch (e) {
					return { error: "Invalid URL format" };
				}
			}

			// CRITICAL: We must return BEFORE navigating, because frappe.set_route()
			// will destroy this JS context (page reload/SPA navigation).
			// We use setTimeout to ensure the return happens first.
			const result = {
				navigated: true,
				target_url: targetUrl,
				message: "Navigation initiated. Use browser_get_page_context to see the new page.",
			};

			// Schedule navigation after this handler returns
			setTimeout(() => {
				logger.debug(`Executing deferred navigation to: ${targetUrl}`);
				window.frappe.set_route(targetUrl);
			}, 100);

			return result;
		},

		/**
		 * Take a screenshot of the page
		 * Uploads to server and returns file reference
		 * Use extract_file_content with operation 'ocr' to read the content
		 */
		async take_screenshot(params) {
			try {
				// Determine what to capture
				let element = document.body;
				if (params.selector) {
					element = document.querySelector(params.selector);
					if (!element) {
						return { error: `Element not found: ${params.selector}` };
					}
				}

				// Check html2canvas can load
				let html2canvas;
				try {
					html2canvas = await loadHtml2canvas();
				} catch (loadError) {
					logger.error("html2canvas failed to load:", loadError);
					return {
						error: "Screenshot capability not available. html2canvas library not loaded.",
						fallback: {
							page_title: document.title,
							url: window.location.href,
							viewport: { width: window.innerWidth, height: window.innerHeight },
						},
					};
				}

				// Show overlay so user knows capture is in progress
				const overlay = document.createElement("div");
				overlay.id = SCREENSHOT_OVERLAY_ID;
				overlay.textContent = window.__ ? window.__("Capturing screenshot...") : "Capturing screenshot...";
				overlay.style.cssText =
					"position:fixed;bottom:16px;right:16px;z-index:2147483647;padding:8px 14px;" +
					"border-radius:999px;background:#1f2937;color:#fff;font:13px/1.2 sans-serif;" +
					"pointer-events:none;";
				document.body.appendChild(overlay);

				// Yield to browser render loop so overlay paints before html2canvas blocks the thread
				await new Promise((resolve) =>
					requestAnimationFrame(() => requestAnimationFrame(resolve))
				);

				// Capture screenshot (hide widget in cloned DOM so it doesn't appear)
				let canvas;
				try {
					canvas = await (await loadHtml2canvas())(element, {
						useCORS: true,
						// NOT allowTaint: it lets cross-origin pixels into the
						// canvas and then toBlob throws SecurityError on the
						// tainted result. useCORS alone degrades gracefully.
						allowTaint: false,
						// html2canvas defaults scale to devicePixelRatio (2 on
						// HiDPI). A full-page Desk list at 2x is tens of
						// megapixels — tens of seconds to rasterize, and past
						// the browser's max canvas size toBlob returns null.
						scale: Math.min(window.devicePixelRatio || 1, MAX_SCREENSHOT_SCALE),
						// Default is 15s PER IMAGE. One slow remote asset on the
						// page was enough to blow the whole tool budget.
						imageTimeout: SCREENSHOT_IMAGE_TIMEOUT_MS,
						logging: false,
						scrollY: params.full_page ? 0 : -window.scrollY,
						windowHeight: params.full_page
							? Math.min(document.body.scrollHeight, MAX_SCREENSHOT_HEIGHT_PX)
							: window.innerHeight,
						onclone: (clonedDoc) => {
							for (const selector of SCREENSHOT_HIDDEN_SELECTORS) {
								const el = clonedDoc.querySelector(selector);
								if (el) el.style.display = "none";
							}
						},
					});
				} finally {
					overlay.remove();
				}

				const quality = (params.quality || 80) / 100;
				const blob = await new Promise((resolve) =>
					canvas.toBlob(resolve, "image/jpeg", quality)
				);

				// toBlob yields null when the canvas exceeds the browser's max
				// size. Without this check `new File([null])` uploads the
				// 4-byte string "null", which the upload endpoint then rejects
				// as a magic-byte mismatch — a size problem wearing a
				// validation error's clothes.
				if (!blob) {
					return {
						error:
							"Screenshot too large to encode. Retry with full_page=false or a selector.",
						width: canvas.width,
						height: canvas.height,
					};
				}

				// Create FormData for upload (same as user attachments)
				const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
				const filename = `screenshot_${timestamp}.jpg`;
				const file = new File([blob], filename, { type: "image/jpeg" });

				const formData = new FormData();
				formData.append("file", file);

				// Upload using existing attachment API
				try {
					const response = await fetch(
						"/api/method/frappe_assistant_core.chat.api.settings.uploads.upload_message_file",
						{
							method: "POST",
							body: formData,
							headers: {
								"X-Frappe-CSRF-Token": window.frappe.csrf_token,
							},
						}
					);

					const result = await response.json();

					if (result.message && result.message.success) {
						const fileData = result.message.file;

						return {
							success: true,
							file_url: fileData.file_url,
							file_name: fileData.file_name,
							width: canvas.width,
							height: canvas.height,
							mime_type: "image/jpeg",
						};
					} else {
						return {
							error:
								"Screenshot upload failed: " +
								(result.message?.error || "Unknown error"),
							width: canvas.width,
							height: canvas.height,
						};
					}
				} catch (uploadError) {
					logger.error("Screenshot upload error:", uploadError);
					return {
						error: `Screenshot upload failed: ${uploadError.message}`,
						width: canvas.width,
						height: canvas.height,
					};
				}
			} catch (error) {
				return { error: `Screenshot failed: ${error.message}` };
			}
		},

		/**
		 * One call, every signal a screen problem needs.
		 *
		 * A screenshot alone is the weakest of the three: Frappe truncates the
		 * traceback in its error dialog, and the payload that actually names the
		 * failure lives in the XHR response the recorder already holds.
		 */
		async capture_diagnostics(params) {
			const recorder = window.FACODiagnostics;
			const snap = recorder
				? recorder.snapshot({
						since_seconds: params.since_seconds || 120,
						max_console: params.max_console || 20,
						max_network: params.max_network || 20,
				  })
				: { enabled: false, console: [], network: [] };

			const context = pageContext.detect_context();
			const result = {
				page: {
					page_type: context.type,
					url: window.location.href,
					route: window.frappe ? window.frappe.get_route() : null,
					doctype: context.doctype || null,
					docname: context.docname || null,
				},
				diagnostics_enabled: snap.enabled,
				console: snap.console,
				network: snap.network,
			};

			if (params.include_screenshot === false) {
				return result;
			}

			// Already approved as part of this call — the screenshot handler is
			// invoked directly rather than routed, so it must not prompt again.
			const shot = await FACOBrowserTools.handlers.take_screenshot({
				full_page: false,
				quality: params.quality || 70,
			});

			if (shot && shot.error) {
				result.screenshot_error = shot.error;
			} else if (shot) {
				result.screenshot = {
					file_url: shot.file_url,
					width: shot.width,
					height: shot.height,
				};
			}

			return result;
		},

		/**
		 * Wait for page to finish loading
		 * Note: We use FACOBrowserTools explicitly instead of `this` because
		 * handlers are called with `handler.call(self.handlers, params)`
		 */
		async wait_for_page(params) {
			const timeout = params.timeout_ms || 10000;

			try {
				// IMPORTANT: Use FACOBrowserTools explicitly, not `this`
				// because `this` refers to the handlers object, not FACOBrowserTools
				await FACOBrowserTools.wait_for_page_ready(timeout, params);

				// Return page context once ready
				const context = pageContext.detect_context();
				return {
					ready: true,
					page_type: context.type,
					url: window.location.href,
					...context,
				};
			} catch (error) {
				return {
					ready: false,
					error: error.message,
				};
			}
		},
	},

	/**
	 * Wait for page to be ready
	 * @param {number} timeout - Max wait time in ms
	 * @param {Object} options - Wait options
	 */
	wait_for_page_ready(timeout, options = {}) {
		return new Promise((resolve, reject) => {
			const startTime = Date.now();

			const check = () => {
				// Check timeout
				if (Date.now() - startTime > timeout) {
					reject(new Error("Timeout waiting for page"));
					return;
				}

				// Check if page is ready
				const isReady = FACOBrowserTools.is_page_ready(options);
				if (isReady) {
					resolve();
					return;
				}

				// Check again in 100ms
				setTimeout(check, 100);
			};

			check();
		});
	},

	/**
	 * Check if page is ready
	 */
	is_page_ready(options = {}) {
		// Basic DOM ready check
		if (document.readyState !== "complete") {
			return false;
		}

		// Check for Frappe page ready
		if (window.frappe && window.frappe.page_ready === false) {
			return false;
		}

		// Check for pending AJAX requests
		if (window.frappe && window.frappe.request && window.frappe.request.count > 0) {
			return false;
		}

		// Check for specific text if requested
		if (options.wait_for_text) {
			if (!document.body.innerText.includes(options.wait_for_text)) {
				return false;
			}
		}

		// Check for specific selector if requested
		if (options.wait_for_selector) {
			if (!document.querySelector(options.wait_for_selector)) {
				return false;
			}
		}

		return true;
	},

	/**
	 * Flag to prevent double initialization
	 */
	_initialized: false,

	/**
	 * Unique instance ID to track which browser tab is processing
	 */
	_instanceId: Math.random().toString(36).substring(2, 8),

	/**
	 * Track processed call_ids to prevent duplicate processing across tabs
	 */
	_processedCalls: new Set(),

	/**
	 * Initialize browser tools - set up Socket.IO listener
	 * This is called automatically when the script loads (see bottom of file)
	 */
	initialize() {
		// Prevent double initialization
		if (this._initialized) {
			logger.debug("Already initialized, skipping");
			return;
		}

		// Check if frappe.realtime AND its socket are available
		// CRITICAL: frappe.realtime.on() silently does nothing if socket is undefined!
		if (!window.frappe || !window.frappe.realtime || !window.frappe.realtime.socket) {
			logger.warn("frappe.realtime.socket not available yet");
			return;
		}

		// Use explicit reference to FACOBrowserTools to avoid `this` binding issues
		const self = FACOBrowserTools;

		// Register Socket.IO listener (fast path — immediate delivery)
		window.frappe.realtime.on("faco_browser_tool_call", (data) => {
			self._handleToolCall(data);
		});

		this._initialized = true;
		logger.debug(`[${this._instanceId}] Initialized - listener registered`);

		// Check for pending calls that arrived before the widget was ready
		// (e.g., after page navigation from SPA, or tool call during page load)
		setTimeout(() => self._processPendingCalls(), 500);
	},

	/**
	 * Handle a single tool call — used by both Socket.IO listener and pending queue.
	 * Deduplicates via _processedCalls Set.
	 */
	async _handleToolCall(data) {
		const { call_id, tool_name, params } = data;

		// A call addressed to a conversation may only be answered by the tab
		// holding it — otherwise another tab reports its own page. Defence in
		// depth; the task_progress room scoping is the primary filter.
		const sid = deps.getSessionId();
		if (data.session_id && sid && data.session_id !== sid) {
			return;
		}

		// Check if this call was already processed (duplicate from Socket.IO + Redis)
		if (this._processedCalls.has(call_id)) {
			return;
		}
		this._processedCalls.add(call_id);

		// Clean up old call_ids after 60 seconds to prevent memory leaks
		setTimeout(() => this._processedCalls.delete(call_id), 60000);

		// Tell the server we have the call. Until this lands it cannot tell
		// "widget isn't listening" from "user hasn't clicked yet", and has to
		// budget every call for the worst case.
		this.report_progress(call_id, "received");

		logger.debug(`[${this._instanceId}] Executing: ${tool_name} (call_id: ${call_id})`);

		try {
			const handler = this.handlers[tool_name];
			if (!handler) {
				logger.error(`Unknown tool: ${tool_name}`);
				await this.submit_result(call_id, null, `Unknown browser tool: ${tool_name}`);
				return;
			}

			// FACO-H5: gate high-risk tools behind a user confirmation.
			if (this._requiresConfirmation(tool_name)) {
				// The server suspends its short delivery deadline while a human
				// is deciding — without this the approval card routinely outlived
				// the tool's budget and every screenshot "timed out".
				this.report_progress(call_id, "awaiting_user");
				const decision = await this._requestUserConfirmation(tool_name, params || {});
				if (decision === "deny") {
					await this.submit_result(
						call_id,
						null,
						"User declined to execute this browser tool. Ask before attempting again."
					);
					return;
				}
				// 'approve' or 'trust' — fall through and execute.
			}

			this.report_progress(call_id, "executing");
			const result = await handler.call(this.handlers, params || {});

			if (result && result.error) {
				await this.submit_result(call_id, null, result.error);
			} else {
				await this.submit_result(call_id, result, null);
			}
		} catch (error) {
			logger.error(`Tool execution failed:`, error);
			await this.submit_result(call_id, null, error.message);
		}
	},

	/**
	 * Decide whether a tool needs user confirmation before executing.
	 * Tools already trusted for the current session short-circuit to false.
	 */
	_requiresConfirmation(tool_name) {
		if (!TOOLS_REQUIRING_CONFIRMATION.has(tool_name)) return false;
		if (this._trustedThisSession.has(tool_name)) return false;
		return true;
	},

	/**
	 * Ask the host to prompt the user and resolve with one of
	 * 'approve' | 'trust' | 'deny'. The host opens the panel if it is closed —
	 * a silent prompt defeats the purpose. 'trust' is remembered per session.
	 */
	async _requestUserConfirmation(tool_name, params) {
		let decision;
		try {
			decision = await deps.confirm({
				tool_name,
				params,
				description: this._describeParams(tool_name, params),
			});
		} catch (e) {
			// Fail closed: a broken prompt must never read as consent.
			logger.warn("Confirmation failed; denying tool call by default.", e);
			return "deny";
		}
		// Anything but an explicit approve/trust is a refusal: the gate must not
		// read an undefined or misspelt decision as consent.
		if (decision !== "approve" && decision !== "trust") {
			return "deny";
		}
		if (decision === "trust") {
			this._trustedThisSession.add(tool_name);
		}
		return decision;
	},

	/**
	 * Best-effort human summary of tool params for the confirmation card.
	 * Keeps the string short so it fits in the card without overflowing.
	 */
	_describeParams(tool_name, params) {
		if (tool_name === "take_screenshot") {
			const selector = params && params.selector;
			const full = params && params.full_page;
			if (selector) return "Region: " + String(selector);
			if (full) return "Full page (including off-screen content)";
			return "Visible viewport only";
		}
		if (tool_name === "get_form_data") {
			const fields = params && params.fields;
			if (Array.isArray(fields) && fields.length > 0) {
				return (
					"Fields: " + fields.slice(0, 5).join(", ") + (fields.length > 5 ? " …" : "")
				);
			}
			return "All fields on the current record";
		}
		if (tool_name === "capture_diagnostics") {
			const seconds = (params && params.since_seconds) || 120;
			return params && params.include_screenshot === false
				? `Console + network from the last ${seconds}s`
				: `Console + network from the last ${seconds}s, plus a screenshot`;
		}
		return "";
	},

	/**
	 * Tight HTML escape for attr-free text nodes. We intentionally do NOT
	 * depend on DOMPurify here — this path is on the critical security
	 * boundary and must keep working even if DOMPurify fails to load.
	 */
	_escapeHtml(text) {
		return String(text || "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");
	},

	/**
	 * Fetch and process any pending tool calls from Redis.
	 * Called on widget initialization to catch up on calls that were sent
	 * while the widget was not active (e.g., after page navigation).
	 */
	async _processPendingCalls() {
		try {
			const sid = deps.getSessionId();
			const response = await window.frappe.call({
				method: "frappe_assistant_core.plugins.faco.tools.browser_bridge.get_pending_browser_tool_calls",
				args: { session_id: sid || null },
			});

			const pendingCalls = response.message || [];
			if (pendingCalls.length === 0) return;

			logger.debug(
				`[${this._instanceId}] Processing ${pendingCalls.length} pending call(s)`
			);

			for (const call of pendingCalls) {
				await this._handleToolCall(call);
			}
		} catch (e) {
			// Not critical — calls will time out naturally on the server side
			logger.warn("Failed to fetch pending calls:", e);
		}
	},

	/**
	 * Report progress on an in-flight call so the server can budget the right
	 * phase. Deliberately fire-and-forget: this is telemetry for the waiter's
	 * deadline, never a gate on execution, so a failed report must not delay or
	 * block the tool. The server only ever extends its deadline, so reports
	 * arriving out of order are harmless.
	 *
	 * @param {string} call_id
	 * @param {"received"|"awaiting_user"|"executing"} state
	 */
	report_progress(call_id, state) {
		try {
			window.frappe.call({
				method: "frappe_assistant_core.plugins.faco.tools.browser_bridge.submit_browser_tool_ack",
				args: { call_id: call_id, state: state },
			});
		} catch (e) {
			logger.debug(`Progress report '${state}' failed for ${call_id}:`, e);
		}
	},

	/**
	 * Submit tool result back to server with retry logic
	 * @param {string} call_id - The call ID to respond to
	 * @param {Object|null} result - The result object (if successful)
	 * @param {string|null} error - The error message (if failed)
	 * @param {number} retries - Number of retry attempts (default: 3)
	 */
	async submit_result(call_id, result, error, retries = 3) {
		for (let attempt = 1; attempt <= retries; attempt++) {
			try {
				// Build args, only including non-null values
				// Frappe's type validation rejects empty strings for Dict types
				const args = { call_id: call_id };
				if (result !== null && result !== undefined) {
					args.result = result;
				}
				if (error !== null && error !== undefined) {
					args.error = error;
				}

				logger.debug(
					`[${FACOBrowserTools._instanceId}] Submitting result for call_id: ${call_id} (attempt ${attempt}/${retries})`
				);
				logger.debug(
					`[${FACOBrowserTools._instanceId}] Result type: ${typeof result}, keys: ${
						result ? Object.keys(result) : "null"
					}`
				);

				await window.frappe.call({
					method: "frappe_assistant_core.plugins.faco.tools.browser_bridge.submit_browser_tool_result",
					args: args,
				});

				logger.debug(
					`[${FACOBrowserTools._instanceId}] Result submitted successfully for call_id: ${call_id}`
				);
				return; // Success - exit the retry loop
			} catch (e) {
				logger.error(
					`[${FACOBrowserTools._instanceId}] Attempt ${attempt}/${retries} failed for call_id ${call_id}:`,
					e
				);

				if (attempt === retries) {
					logger.error(
						`[${FACOBrowserTools._instanceId}] All ${retries} retries exhausted for call_id: ${call_id}`
					);
				} else {
					// Exponential backoff: 500ms, 1000ms, 1500ms...
					const delay = 500 * attempt;
					logger.debug(`Retrying in ${delay}ms...`);
					await new Promise((resolve) => setTimeout(resolve, delay));
				}
			}
		}
	},
};

export function startBrowserTools(nextDeps) {
	// An omitted dep keeps its fail-closed default rather than becoming undefined.
	const provided = Object.fromEntries(
		Object.entries(nextDeps || {}).filter(([, v]) => v !== undefined)
	);
	deps = { ...deps, ...provided };
	// frappe.realtime.on() is a silent no-op until the socket exists, so wait
	// for it (up to 10s), exactly as the old self-starting script did.
	let polls = 0;
	const tick = () => {
		if (window.frappe && window.frappe.realtime && window.frappe.realtime.socket) {
			FACOBrowserTools.initialize();
			return;
		}
		if (++polls >= 100) {
			logger.warn("Browser tools: frappe.realtime.socket not available after 10s");
			return;
		}
		setTimeout(tick, 100);
	};
	tick();
}

export default FACOBrowserTools;
