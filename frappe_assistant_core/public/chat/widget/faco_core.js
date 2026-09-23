// Frappe Assistant Copilot - Powered by FAC Cloud - Shared streaming and API logic
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

/**
 * FACOCore - Shared functionality for FACO widget and full-page assistant
 *
 * This module provides:
 * - Socket.IO streaming handlers
 * - Message formatting
 * - API wrappers
 * - Session management
 */
// DOMPurify configuration for LLM-rendered markdown.
//
// Why an allowlist: the widget used to call $.html() on raw Showdown output
// (see 2026-04-21 FACO security audit, FACO-C5). Showdown's raw-HTML-
// passthrough mode made every assistant message a stored-XSS vector. We
// sanitise at the single render boundary — FACOCore.format_message — so
// downstream sinks (widget_streaming, widget_richblocks, widget_onboarding)
// stay unchanged. The config preserves the markdown/rich-block element set
// while dropping <script>, event handlers (onerror=, onclick=, …), inline
// javascript: and data: URIs, and framing tags.
const _FACO_PURIFY_CONFIG = {
	ALLOWED_TAGS: [
		"a",
		"b",
		"blockquote",
		"br",
		"code",
		"del",
		"details",
		"div",
		"em",
		"h1",
		"h2",
		"h3",
		"h4",
		"h5",
		"h6",
		"hr",
		"i",
		"img",
		"ins",
		"li",
		"ol",
		"p",
		"pre",
		"s",
		"span",
		"strong",
		"sub",
		"summary",
		"sup",
		"table",
		"tbody",
		"td",
		"tfoot",
		"th",
		"thead",
		"tr",
		"u",
		"ul",
	],
	ALLOWED_ATTR: [
		"href",
		"target",
		"rel",
		"title",
		"alt",
		"src",
		"class",
		"id",
		"colspan",
		"rowspan",
		"align",
		"open",
	],
	// Force-open user links in a new tab with a safe rel (DOMPurify native hook).
	ADD_ATTR: ["target"],
	ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|ftp|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
	FORBID_TAGS: [
		"script",
		"iframe",
		"object",
		"embed",
		"style",
		"form",
		"input",
		"textarea",
		"button",
		"link",
		"meta",
	],
	FORBID_ATTR: [
		"onerror",
		"onload",
		"onclick",
		"onmouseover",
		"onfocus",
		"onblur",
		"onchange",
		"onsubmit",
		"srcdoc",
	],
};

let _faco_purify_hooks_installed = false;

function _faco_install_purify_hooks() {
	if (_faco_purify_hooks_installed) return;
	if (typeof DOMPurify === "undefined" || !DOMPurify.addHook) return;

	// Harden links rendered from assistant markdown:
	//   - force target="_blank" (opens in new tab, keeps Desk alive)
	//   - force rel="noopener noreferrer" to block reverse tabnabbing
	DOMPurify.addHook("afterSanitizeAttributes", function (node) {
		if (node.tagName === "A" && node.hasAttribute("href")) {
			node.setAttribute("target", "_blank");
			node.setAttribute("rel", "noopener noreferrer");
		}
	});

	_faco_purify_hooks_installed = true;
}

// A single pass leaves a tag behind whenever removing one splices a new one
// together — "<scr<script>ipt>" becomes "<script>". Repeat to a fixpoint so
// the result cannot contain a tag however the input was nested.
function _strip_tags_completely(text) {
	let previous;
	do {
		previous = text;
		text = text.replace(/<[^>]*>/g, "");
	} while (text !== previous);
	return text;
}

function _faco_sanitize_html(html) {
	if (typeof DOMPurify === "undefined" || !DOMPurify.sanitize) {
		// Fail closed: if DOMPurify failed to load, strip ALL tags rather
		// than serving raw Showdown output. The widget degrades to plain
		// text but stays XSS-safe.
		return _strip_tags_completely(String(html || ""));
	}
	_faco_install_purify_hooks();
	return DOMPurify.sanitize(html, _FACO_PURIFY_CONFIG);
}

window.FACOCore = {
	// Markdown converter instance (shared)
	markdown_converter: null,

	/**
	 * Initialize the markdown converter with table support
	 */
	init_markdown() {
		if (this.markdown_converter) return this.markdown_converter;

		if (frappe.md2html) {
			const ShowdownConstructor = frappe.md2html.constructor;
			this.markdown_converter = new ShowdownConstructor({
				tables: true,
				strikethrough: true,
				tasklists: true,
				smoothLivePreview: true,
				simpleLineBreaks: false,
				openLinksInNewWindow: true,
			});
		} else {
			// Initialize frappe.md2html if not yet created
			frappe.markdown("");
			if (frappe.md2html) {
				const ShowdownConstructor = frappe.md2html.constructor;
				this.markdown_converter = new ShowdownConstructor({
					tables: true,
					strikethrough: true,
					tasklists: true,
					smoothLivePreview: true,
					simpleLineBreaks: false,
					openLinksInNewWindow: true,
				});
			}
		}
		return this.markdown_converter;
	},

	/**
	 * Format message content with markdown for assistant messages
	 * @param {string} content - Message content
	 * @param {string} role - 'user' or 'assistant'
	 * @returns {string} HTML-formatted content
	 */
	format_message(content, role = "user") {
		if (role === "assistant") {
			// Rich blocks: route through the rich block parser when available.
			// Rich-block renderers already _escapeHtml attrs and recurse
			// through format_message for bodies, so the end-to-end output
			// still passes through the sanitiser below.
			if (window.FACOWidgetRichBlocks && window.FACOWidgetRichBlocks.hasBlocks(content)) {
				return _faco_sanitize_html(window.FACOWidgetRichBlocks.process(content));
			}

			this.init_markdown();

			let html;
			if (this.markdown_converter) {
				html = this.markdown_converter.makeHtml(content);
			} else {
				html = frappe.markdown(content);
			}

			// Wrap tables in scrollable container
			html = html.replace(/<table>/g, '<div class="table-wrapper"><table>');
			html = html.replace(/<\/table>/g, "</table></div>");

			return _faco_sanitize_html(html);
		}

		// Simple formatting for user messages. User-supplied text can contain
		// angle brackets (</script>, <img onerror=…>) when users paste code or
		// craft messages — sanitise before the widget echoes their own input
		// back to them.
		let formatted = content
			.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
			.replace(/\*(.*?)\*/g, "<em>$1</em>")
			.replace(/`(.*?)`/g, "<code>$1</code>")
			.replace(/\n/g, "<br>");

		// Convert URLs to links
		formatted = formatted.replace(
			/(https?:\/\/[^\s]+)/g,
			'<a href="$1" target="_blank">$1</a>'
		);

		return _faco_sanitize_html(formatted);
	},

	/**
	 * Format timestamp for display
	 * @param {Date} date - Date object
	 * @returns {string} Formatted time string
	 */
	format_time(date) {
		return date.toLocaleTimeString("en-US", {
			hour: "numeric",
			minute: "2-digit",
			hour12: true,
		});
	},

	/**
	 * Generate a unique session ID
	 *
	 * The random half comes from crypto.getRandomValues, not Math.random: a
	 * session id names a conversation and is handed between the widget, the
	 * SPA and AR, so it should not be predictable from the clock. Unlike
	 * crypto.randomUUID, getRandomValues needs no secure context, so this
	 * works on an http:// dev bench too.
	 *
	 * @returns {string} Session ID
	 */
	generate_session_id() {
		const bytes = new Uint8Array(9);
		crypto.getRandomValues(bytes);
		const random = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
		return "faco_" + Date.now() + "_" + random;
	},

	/**
	 * Get stored active session ID (for switching between widget and full page).
	 * Same-tab hand-off — uses sessionStorage so other tabs don't inherit the
	 * session id (cross-tab continuity is not a use case). Returns the id only
	 * when the user who stored it is still the one logged in; sessionStorage
	 * outlives a login, and a session id names no user of its own.
	 */
	get_active_session() {
		try {
			const entry = FACOWidgetSession.decode(
				sessionStorage.getItem("faco_active_session")
			);
			return FACOWidgetSession.owned(entry, frappe.session.user);
		} catch (e) {
			return null;
		}
	},

	set_active_session(session_id) {
		try {
			sessionStorage.setItem(
				"faco_active_session",
				FACOWidgetSession.encode(session_id, frappe.session.user)
			);
		} catch (e) {
			// Silently fail
		}
	},

	clear_active_session() {
		try {
			sessionStorage.removeItem("faco_active_session");
		} catch (e) {
			// Silently fail
		}
	},

	// --- API Methods ---

	/**
	 * Check if user can use FACO
	 * @returns {Promise<Object>} Access info
	 */
	async check_access() {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.settings.access.can_use_faco",
				type: "GET",
				args: {},
			});
			return response.message;
		} catch (error) {
			return { can_use: false, reason: "Error checking access" };
		}
	},

	/**
	 * Load widget/UI settings from server
	 * @returns {Promise<Object>} Settings object
	 */
	async load_settings() {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.settings.widget.get_widget_settings",
				type: "GET",
				args: {},
			});
			return response.message || this.get_default_settings();
		} catch (error) {
			return this.get_default_settings();
		}
	},

	/**
	 * Default settings fallback
	 * @returns {Object} Default settings
	 */
	get_default_settings() {
		return {
			button: {
				size: 56,
				icon: "robot",
				enable_pulse: true,
				shadow: "0 4px 20px rgba(0,0,0,0.15)",
			},
			window: {
				width: 400,
				height: 650,
				border_radius: 12,
				font_size: "14px",
			},
			messages: {},
			custom_css: "",
		};
	},

	/**
	 * Load session history
	 * @param {string} session_id - Session ID
	 * @returns {Promise<Array>} Array of messages
	 */
	async load_session_history(session_id) {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.chat.sessions.get_session_history",
				type: "GET",
				args: { session_id },
			});
			return response.message || [];
		} catch (error) {
			return [];
		}
	},

	/**
	 * Get user's recent sessions for history sidebar
	 * @param {number} limit - Maximum sessions to return
	 * @returns {Promise<Array>} Array of sessions
	 */
	async get_user_sessions(limit = 20) {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.chat.sessions.get_user_sessions",
				type: "GET",
				args: { limit },
			});
			return response.message || [];
		} catch (error) {
			return [];
		}
	},

	/**
	 * Send a message to FACO
	 * @param {Object} params - Message parameters
	 * @returns {Promise<Object>} Response
	 */
	async send_message({ session_id, message, context, include_context = true, file_urls = [] }) {
		return frappe.call({
			method: "frappe_assistant_core.chat.api.chat.messages.send_message",
			args: {
				session_id,
				message,
				context: include_context && context ? JSON.stringify(context) : null,
				include_context,
				file_urls: JSON.stringify(file_urls),
			},
		});
	},

	/**
	 * Upload a file for message attachment
	 * @param {File} file - File to upload
	 * @returns {Promise<Object>} Upload result
	 */
	async upload_file(file) {
		const formData = new FormData();
		formData.append("file", file);

		const response = await fetch(
			"/api/method/frappe_assistant_core.chat.api.settings.uploads.upload_message_file",
			{
				method: "POST",
				headers: {
					"X-Frappe-CSRF-Token": frappe.csrf_token,
				},
				body: formData,
			}
		);

		return response.json();
	},

	/**
	 * Get suggested prompts based on context
	 * @param {Object} context - Page context
	 * @returns {Promise<Array>} Array of prompt suggestions
	 */
	async get_suggested_prompts(context) {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.prompts.get_suggested_prompts",
				type: "GET",
				args: { context: JSON.stringify(context) },
			});
			return response.message || [];
		} catch (error) {
			return [];
		}
	},

	// --- Avatar Helpers ---

	/**
	 * Get user avatar HTML
	 * @returns {string} HTML for user avatar
	 */
	get_user_avatar() {
		const user_image = frappe.user_info(frappe.session.user).image;
		if (user_image) {
			return `<img src="${user_image}" alt="User" />`;
		}
		return `<div class="avatar-placeholder">${frappe.session.user[0].toUpperCase()}</div>`;
	},

	/**
	 * Get assistant avatar HTML (robot icon)
	 * @returns {string} HTML for assistant avatar
	 */
	get_assistant_avatar() {
		return `
			<div class="faco-robot faco-robot-message">
				<div class="robot-antenna">
					<div class="robot-antenna-tip"></div>
				</div>
				<div class="robot-arm robot-arm-left"></div>
				<div class="robot-arm robot-arm-right"></div>
				<div class="robot-head">
					<div class="robot-screen">
						<div class="robot-brow robot-brow-left"></div>
						<div class="robot-brow robot-brow-right"></div>
						<div class="robot-eye robot-eye-left"></div>
						<div class="robot-eye robot-eye-right"></div>
						<div class="robot-mouth"></div>
					</div>
				</div>
				<div class="robot-body"></div>
			</div>
		`;
	},

	// --- Context Extraction ---

	/**
	 * The Desk form currently on screen, or null when the route is not a form.
	 *
	 * Single accessor for the whole widget. Resolves the form from the routed
	 * form page rather than reading the `cur_frm` global directly: Frappe
	 * deprecates `cur_frm` because it holds whichever form last called
	 * refresh(), so it outlives navigation away from that form and can name a
	 * DocType the user is no longer looking at. Gating on the route first means
	 * the widget never hands the assistant stale form context.
	 *
	 * @returns {Object|null} A frappe.ui.form.Form with a loaded doc, or null.
	 */
	get_current_form() {
		const route = (frappe.get_route && frappe.get_route()) || [];
		if (route[0] !== "Form") return null;

		const layout = (frappe.router && frappe.router.doctype_layout) || route[1];
		const page = frappe.views && frappe.views.formview && frappe.views.formview[layout];
		// Fall back to the global only when the form page has not been
		// registered yet — the route says Form, so it cannot be stale here.
		// nosemgrep: frappe-cur-frm-usage
		const frm = (page && page.frm) || window.cur_frm;

		return frm && frm.doc ? frm : null;
	},

	/**
	 * Detect current page context
	 * @returns {Object} Context object
	 */
	get_page_context() {
		const route = frappe.get_route() || [];
		const frm = this.get_current_form();

		if (frm) {
			return {
				type: "Form",
				doctype: frm.doctype,
				name: frm.doc.name,
				url: window.location.href,
				is_new: frm.is_new(),
			};
		} else if (route && route[0] === "List") {
			return {
				type: "List",
				doctype: route[1],
				url: window.location.href,
				has_list_view: window.cur_list ? true : false,
			};
		} else if (route && route[0] === "query-report") {
			return {
				type: "Report",
				name: route[1],
				url: window.location.href,
			};
		} else if (route && route[0] === "Tree" && route[1]) {
			return {
				type: "Tree",
				doctype: route[1],
				url: window.location.href,
			};
		} else if (
			(route && route[0] === "Workspaces") ||
			(route && route.length === 0) ||
			route[0] === "workspace"
		) {
			return {
				type: "Workspace",
				workspace_name: route[1] || "Home",
				url: window.location.href,
			};
		} else if (route && route[0] === "dashboard") {
			return {
				type: "Dashboard",
				dashboard_name: route[1],
				url: window.location.href,
			};
		} else if (route && route[0] === "print") {
			return {
				type: "Print",
				doctype: route[1],
				name: route[2],
				print_format: route[3],
				url: window.location.href,
			};
		} else if (route && frappe.pages && frappe.pages[route[0]]) {
			return {
				type: "Custom Page",
				page_name: route[0],
				url: window.location.href,
			};
		} else if (window.cur_page && window.cur_page.page) {
			return {
				type: "Page",
				page_name: window.cur_page.page.page_name || route[0] || "Unknown",
				url: window.location.href,
			};
		} else {
			return {
				type: "General",
				route: route,
				url: window.location.href,
				page_title: document.title,
			};
		}
	},

	/**
	 * Get context description text
	 * @param {Object} context - Context object
	 * @returns {string} Human-readable context description
	 */
	get_context_text(context) {
		if (!context || context.type === "General") return "";

		switch (context.type) {
			case "Form":
				return `Viewing ${context.doctype}: ${context.name}`;
			case "List":
				return `Viewing ${context.doctype} list`;
			case "Report":
				return `Viewing report: ${context.name}`;
			case "Tree":
				return `Viewing ${context.doctype} tree`;
			case "Workspace":
				return `Workspace: ${context.workspace_name}`;
			case "Dashboard":
				return `Dashboard: ${context.dashboard_name}`;
			case "Print":
				return `Print: ${context.doctype} - ${context.name}`;
			case "Custom Page":
			case "Page":
				return `Page: ${context.page_name}`;
			default:
				return "";
		}
	},
};
