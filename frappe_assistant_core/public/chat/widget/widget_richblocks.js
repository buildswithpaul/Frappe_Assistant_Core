// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Rich Blocks
// Renders callout, metric, steps, accordion, tabs, mermaid, and chart
// code fence blocks as styled HTML in the vanilla JS widget.

/**
 * FACOWidgetRichBlocks - Rich block parsing and rendering for the desk widget
 *
 * Ports the Vue SPA's parser.js + registry.js architecture to vanilla JS,
 * outputting HTML strings instead of Vue component instances.
 */
window.FACOWidgetRichBlocks = {
	// --- SVG Icons ---

	_icons: {
		info: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
		warning:
			'<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>',
		tip: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>',
		success:
			'<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
		error: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
		trendUp:
			'<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/></svg>',
		trendDown:
			'<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/></svg>',
		check: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>',
		chevron:
			'<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>',
		diagram:
			'<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7"/></svg>',
		chart: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>',
	},

	// --- Attribute Parser ---

	/**
	 * Parse key="value" pairs from code fence attribute string.
	 * e.g. 'type="info" title="Note"' → { type: 'info', title: 'Note' }
	 */
	_parseAttrs(attrString) {
		if (!attrString) return {};
		const attrs = {};
		const re = /(\w+)="([^"]*)"/g;
		let m;
		while ((m = re.exec(attrString)) !== null) {
			attrs[m[1]] = m[2];
		}
		return attrs;
	},

	// --- JSON Body Parser ---

	/**
	 * The model reaches for a JSON body on any fence, having generalised from
	 * `chart`/`mermaid` sitting beside them in the same skill doc. Every block
	 * documenting fence-line attributes has to read a JSON body too, or the
	 * payload lands on the user's screen as visible JSON.
	 *
	 * Returns the parsed object/array, or null for a non-JSON body.
	 */
	_parseJsonBody(body) {
		const trimmed = (body || "").trim();
		if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
		try {
			const parsed = JSON.parse(trimmed);
			return parsed && typeof parsed === "object" ? parsed : null;
		} catch {
			return null;
		}
	},

	/** JSON body as a plain object, or {} for an array / non-JSON body. */
	_jsonObjectBody(body) {
		const parsed = this._parseJsonBody(body);
		return parsed && !Array.isArray(parsed) ? parsed : {};
	},

	/**
	 * First non-empty value for the given keys, attributes before JSON body.
	 * Attributes win because they are the documented dialect — a fence
	 * carrying both is a model hedging, and the explicit form is the intent.
	 */
	_picker(attrs, json) {
		return function () {
			const keys = Array.prototype.slice.call(arguments);
			for (const key of keys) {
				if (attrs[key]) return String(attrs[key]);
			}
			for (const key of keys) {
				const value = json[key];
				if (value !== undefined && value !== null && value !== "") {
					return String(value);
				}
			}
			return "";
		};
	},

	// --- Block Regex (built once) ---

	_blockTypes: ["chart", "mermaid", "callout", "metric", "steps", "accordion", "tabs"],

	_getBlockRegex() {
		if (!this._blockRegex) {
			const types = this._blockTypes.join("|");
			this._blockRegex = new RegExp(
				"```(" + types + ")([ \\t]+[^\\n]*)?\\n([\\s\\S]*?)```",
				"g"
			);
		}
		return this._blockRegex;
	},

	_getTestRegex() {
		if (!this._testRegex) {
			const types = this._blockTypes.join("|");
			this._testRegex = new RegExp("```(?:" + types + ")");
		}
		return this._testRegex;
	},

	// --- HTML Escaping ---

	_escapeHtml(text) {
		const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
		return String(text).replace(/[&<>"']/g, (m) => map[m]);
	},

	// --- Markdown Helper ---

	_renderMarkdown(text) {
		if (!text || !text.trim()) return "";
		return FACOCore.format_message(text, "assistant");
	},

	/** One metric card, or null when neither a title nor a value is given. */
	_metricCard(attrs, json, self) {
		const pick = self._picker(attrs, json);
		const title = pick("title", "label");
		const value = pick("value");
		const change = pick("change", "delta");
		const trend = pick("trend");
		const description = pick("description", "suffix");

		if (!title && !value) return null;

		let trendClass = "faco-rb-trend-flat";
		let trendIcon = "";
		if (trend === "up") {
			trendClass = "faco-rb-trend-up";
			trendIcon = self._icons.trendUp;
		} else if (trend === "down") {
			trendClass = "faco-rb-trend-down";
			trendIcon = self._icons.trendDown;
		}

		let changeHtml = "";
		if (change) {
			changeHtml =
				'<span class="faco-rb-metric-change ' +
				trendClass +
				'">' +
				(trendIcon
					? '<span class="faco-rb-trend-icon">' + trendIcon + "</span>"
					: "") +
				self._escapeHtml(change) +
				"</span>";
		}

		return (
			'<div class="faco-rb-metric">' +
			(title
				? '<div class="faco-rb-metric-title">' + self._escapeHtml(title) + "</div>"
				: "") +
			'<div class="faco-rb-metric-row">' +
			'<span class="faco-rb-metric-value">' +
			self._escapeHtml(value) +
			"</span>" +
			changeHtml +
			"</div>" +
			(description
				? '<div class="faco-rb-metric-desc">' +
				  self._escapeHtml(description) +
				  "</div>"
				: "") +
			"</div>"
		);
	},

	// --- Section Splitter (used by accordion and tabs) ---

	_splitSections(body) {
		if (!body) return [];
		const parts = body.split(/^## /m).filter(Boolean);
		return parts.map((part) => {
			const newlineIdx = part.indexOf("\n");
			if (newlineIdx === -1) {
				return { title: part.trim(), html: "" };
			}
			const title = part.slice(0, newlineIdx).trim();
			const content = part.slice(newlineIdx + 1).trim();
			return {
				title,
				html: content ? this._renderMarkdown(content) : "",
			};
		});
	},

	// --- Block Renderers ---

	_blocks: {
		// Reads a JSON body the same way `metric` does. Without it a
		// `{"type":"warning","title":…,"content":…}` fence rendered an *info*
		// box with no title and the raw JSON as its text. An unrecognised
		// JSON shape keeps its body visible: better the reader sees the raw
		// object than an empty box that looks like a UI fault.
		callout(body, attrs, self) {
			const validTypes = ["info", "warning", "tip", "success", "error"];
			const json = self._jsonObjectBody(body);
			const pick = self._picker(attrs, json);
			const requestedType = pick("type");
			const type = validTypes.includes(requestedType) ? requestedType : "info";
			const title = pick("title", "heading");
			const icon = self._icons[type] || self._icons.info;
			const text = pick("content", "body", "text", "message") || body;
			const renderedBody = text ? self._renderMarkdown(text) : "";

			return (
				'<div class="faco-rb-callout faco-rb-callout-' +
				type +
				'">' +
				'<div class="faco-rb-callout-icon">' +
				icon +
				"</div>" +
				'<div class="faco-rb-callout-content">' +
				(title
					? '<div class="faco-rb-callout-title">' + self._escapeHtml(title) + "</div>"
					: "") +
				(renderedBody
					? '<div class="faco-rb-callout-body">' + renderedBody + "</div>"
					: "") +
				"</div>" +
				"</div>"
			);
		},

		// Data arrives three ways: fence-line attributes (documented), a JSON
		// object keyed on label/value (what the model usually writes, having
		// generalised from `chart`), or a JSON *array* — a whole KPI row in
		// one fence, rendered as one card per entry. The body used to be
		// ignored outright, so both JSON shapes produced an empty card; now
		// an unusable fence returns null and the caller shows a code block.
		metric(body, attrs, self) {
			const parsed = self._parseJsonBody(body);

			if (Array.isArray(parsed)) {
				const cards = parsed
					.map((entry) =>
						self._metricCard(
							attrs,
							entry && typeof entry === "object" ? entry : {},
							self
						)
					)
					.filter(Boolean);
				return cards.length ? cards.join("") : null;
			}

			return self._metricCard(attrs, parsed || {}, self);
		},

		steps(body, attrs, self) {
			const title = attrs.title || "";
			const current = attrs.current ? parseInt(attrs.current, 10) : 0;

			if (!body) return null;

			const stepTexts = body
				.split("\n")
				.map((line) => line.replace(/^\d+\.\s*/, "").trim())
				.filter(Boolean);

			if (stepTexts.length === 0) return null;

			let stepsHtml = "";
			stepTexts.forEach((text, idx) => {
				const num = idx + 1;
				let stepClass = "faco-rb-step";
				let markerContent;

				if (current > 0 && num < current) {
					stepClass += " faco-rb-step-done";
					markerContent =
						'<span class="faco-rb-step-check">' + self._icons.check + "</span>";
				} else if (current > 0 && num === current) {
					stepClass += " faco-rb-step-active";
					markerContent = '<span class="faco-rb-step-number">' + num + "</span>";
				} else {
					markerContent = '<span class="faco-rb-step-number">' + num + "</span>";
				}

				// Render inline markdown for step text
				const rendered = self._renderMarkdown(text);

				stepsHtml +=
					'<li class="' +
					stepClass +
					'">' +
					'<div class="faco-rb-step-marker">' +
					markerContent +
					"</div>" +
					'<div class="faco-rb-step-content">' +
					rendered +
					"</div>" +
					"</li>";
			});

			return (
				'<div class="faco-rb-steps">' +
				(title
					? '<div class="faco-rb-steps-title">' + self._escapeHtml(title) + "</div>"
					: "") +
				'<ol class="faco-rb-steps-list">' +
				stepsHtml +
				"</ol>" +
				"</div>"
			);
		},

		accordion(body, _attrs, self) {
			const sections = self._splitSections(body);
			if (sections.length === 0) return null;

			let html = '<div class="faco-rb-accordion">';
			sections.forEach((section, idx) => {
				const isOpen = idx === 0;
				html +=
					'<div class="faco-rb-accordion-section' +
					(isOpen ? " faco-rb-open" : "") +
					'">' +
					'<button class="faco-rb-accordion-header" type="button">' +
					'<span class="faco-rb-accordion-chevron">' +
					self._icons.chevron +
					"</span>" +
					'<span class="faco-rb-accordion-title">' +
					self._escapeHtml(section.title) +
					"</span>" +
					"</button>" +
					'<div class="faco-rb-accordion-body">' +
					section.html +
					"</div>" +
					"</div>";
			});
			html += "</div>";
			return html;
		},

		tabs(body, attrs, self) {
			const sections = self._splitSections(body);
			if (sections.length === 0) return null;

			// Find default tab by title match
			let activeIdx = 0;
			if (attrs.default) {
				const defaultLower = attrs.default.toLowerCase();
				const matchIdx = sections.findIndex((s) => s.title.toLowerCase() === defaultLower);
				if (matchIdx >= 0) activeIdx = matchIdx;
			}

			let buttonsHtml = "";
			let panelsHtml = "";

			sections.forEach((section, idx) => {
				const isActive = idx === activeIdx;
				buttonsHtml +=
					'<button class="faco-rb-tab-btn' +
					(isActive ? " faco-rb-active" : "") +
					'"' +
					' data-tab-index="' +
					idx +
					'"' +
					' role="tab" aria-selected="' +
					isActive +
					'"' +
					' type="button">' +
					self._escapeHtml(section.title) +
					"</button>";

				panelsHtml +=
					'<div class="faco-rb-tab-panel' +
					(isActive ? " faco-rb-active" : "") +
					'"' +
					' data-tab-index="' +
					idx +
					'"' +
					' role="tabpanel">' +
					section.html +
					"</div>";
			});

			return (
				'<div class="faco-rb-tabs">' +
				'<div class="faco-rb-tabs-bar" role="tablist">' +
				buttonsHtml +
				"</div>" +
				panelsHtml +
				"</div>"
			);
		},

		mermaid(body, _attrs, self) {
			if (!body) return null;

			// Extract diagram type from first line
			const firstWord = body.trim().split(/[\s\n{]/)[0] || "diagram";

			return (
				'<div class="faco-rb-placeholder faco-rb-placeholder-mermaid">' +
				'<div class="faco-rb-placeholder-header">' +
				'<span class="faco-rb-placeholder-icon">' +
				self._icons.diagram +
				"</span>" +
				'<div class="faco-rb-placeholder-info">' +
				'<div class="faco-rb-placeholder-label">Mermaid Diagram</div>' +
				'<div class="faco-rb-placeholder-type">' +
				self._escapeHtml(firstWord) +
				"</div>" +
				"</div>" +
				'<button class="faco-rb-view-full" type="button">View in full assistant</button>' +
				"</div>" +
				'<details class="faco-rb-placeholder-code">' +
				"<summary>Show source</summary>" +
				"<pre><code>" +
				self._escapeHtml(body) +
				"</code></pre>" +
				"</details>" +
				"</div>"
			);
		},

		chart(body, _attrs, self) {
			if (!body) return null;

			let chartType = "chart";
			let chartTitle = "";

			try {
				const config = JSON.parse(body);
				chartType = config.type || "chart";
				chartTitle = config.title || "";
			} catch {
				// Invalid JSON — show as raw code
			}

			const typeLabel = chartTitle
				? self._escapeHtml(chartType) + " — " + self._escapeHtml(chartTitle)
				: self._escapeHtml(chartType);

			return (
				'<div class="faco-rb-placeholder faco-rb-placeholder-chart">' +
				'<div class="faco-rb-placeholder-header">' +
				'<span class="faco-rb-placeholder-icon">' +
				self._icons.chart +
				"</span>" +
				'<div class="faco-rb-placeholder-info">' +
				'<div class="faco-rb-placeholder-label">Chart</div>' +
				'<div class="faco-rb-placeholder-type">' +
				typeLabel +
				"</div>" +
				"</div>" +
				'<button class="faco-rb-view-full" type="button">View in full assistant</button>' +
				"</div>" +
				'<details class="faco-rb-placeholder-code">' +
				"<summary>Show source</summary>" +
				"<pre><code>" +
				self._escapeHtml(body) +
				"</code></pre>" +
				"</details>" +
				"</div>"
			);
		},
	},

	// --- Public API ---

	/**
	 * Lightweight pre-check: does content contain any rich block code fences?
	 * Avoids running the full parser on every streaming chunk.
	 */
	hasBlocks(content) {
		return this._getTestRegex().test(content);
	},

	/**
	 * Parse content for rich blocks and render to HTML.
	 * Returns a complete HTML string with rich blocks + markdown segments.
	 */
	process(content) {
		if (!content) return "";

		const regex = this._getBlockRegex();
		const parts = [];
		let lastIndex = 0;

		// Reset regex state (global regexes are stateful)
		regex.lastIndex = 0;
		let match;

		while ((match = regex.exec(content)) !== null) {
			// Render text before this block as markdown
			if (match.index > lastIndex) {
				const textBefore = content.slice(lastIndex, match.index);
				if (textBefore.trim()) {
					parts.push(this._renderMarkdown(textBefore));
				}
			}

			const blockType = match[1];
			const attrString = match[2] ? match[2].trim() : "";
			const blockBody = match[3].trim();
			const renderer = this._blocks[blockType];

			if (renderer) {
				const attrs = this._parseAttrs(attrString);
				const blockHtml = renderer(blockBody, attrs, this);

				if (blockHtml) {
					parts.push(blockHtml);
				} else {
					// Renderer returned null — render as plain code block
					parts.push(this._renderMarkdown("```\n" + blockBody + "\n```"));
				}
			}

			lastIndex = match.index + match[0].length;
		}

		// Remaining text after last block
		if (lastIndex < content.length) {
			const textAfter = content.slice(lastIndex);
			if (textAfter.trim()) {
				parts.push(this._renderMarkdown(textAfter));
			}
		}

		// No blocks found — render entire content as markdown
		if (parts.length === 0 && content.trim()) {
			return this._renderMarkdown(content);
		}

		return parts.join("");
	},

	/**
	 * Set up jQuery event delegation for interactive blocks.
	 * Called once during widget initialization.
	 */
	initEventDelegation(widget) {
		const $messages = widget.$widget.find(".faco-messages");

		// Accordion toggle
		$messages.on("click", ".faco-rb-accordion-header", function (e) {
			e.preventDefault();
			$(this).closest(".faco-rb-accordion-section").toggleClass("faco-rb-open");
		});

		// Tab switching
		$messages.on("click", ".faco-rb-tab-btn", function (e) {
			e.preventDefault();
			const $btn = $(this);
			const $tabs = $btn.closest(".faco-rb-tabs");
			const idx = $btn.data("tab-index");

			// Deactivate all
			$tabs
				.find(".faco-rb-tab-btn")
				.removeClass("faco-rb-active")
				.attr("aria-selected", "false");
			$tabs.find(".faco-rb-tab-panel").removeClass("faco-rb-active");

			// Activate clicked
			$btn.addClass("faco-rb-active").attr("aria-selected", "true");
			$tabs
				.find('.faco-rb-tab-panel[data-tab-index="' + idx + '"]')
				.addClass("faco-rb-active");
		});

		// "View in full assistant" button for mermaid/chart placeholders
		$messages.on("click", ".faco-rb-view-full", function (e) {
			e.preventDefault();
			if (widget.expand_to_full_page) {
				widget.expand_to_full_page();
			}
		});
	},
};
