// Frappe Assistant Copilot - Widget Slash Menu Module
// Popover above the input that lists prompt templates when the user types "/" at
// the start of the message. Mirrors the SPA's SlashMenu behaviour.

window.FACOWidgetSlashMenu = {
	CATEGORY_ICONS: {
		"data-quality": "🔍",
		documentation: "📄",
		"sales-crm": "📊",
		"hr-payroll": "👥",
		purchasing: "📦",
		manufacturing: "🏭",
	},

	/**
	 * Attach the slash menu to a widget instance. Safe to call once per widget.
	 * @param {Object} widget - FACOWidget instance
	 */
	mount(widget) {
		if (widget._slashMenuMounted) return;
		widget._slashMenuMounted = true;

		const $wrapper = widget.$widget.find(".faco-input-wrapper");
		const $input = widget.$widget.find(".faco-input");
		if (!$wrapper.length || !$input.length) return;

		// Ensure wrapper anchors the absolute popover
		$wrapper.css("position", "relative");

		const $menu = $(`
			<div class="faco-slash-menu" role="listbox" style="display:none;">
				<div class="faco-slash-body"></div>
				<div class="faco-slash-footer">
					<span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
					<span><kbd>⏎</kbd> select</span>
					<span><kbd>esc</kbd> close</span>
				</div>
			</div>
		`);
		$wrapper.prepend($menu);

		const state = {
			open: false,
			activeIndex: 0,
			rows: [], // [{template, element}]
		};

		const close = () => {
			state.open = false;
			state.activeIndex = 0;
			state.rows = [];
			$menu.hide();
		};

		const pickActive = () => {
			const row = state.rows[state.activeIndex];
			if (!row) return;
			this.pick(widget, row.template, $input, close);
		};

		const move = (delta) => {
			const total = state.rows.length;
			if (total === 0) return;
			state.activeIndex = (state.activeIndex + delta + total) % total;
			this.highlight(state);
		};

		// --- Input handler: detect `/query` state ---
		$input.on("input.slashmenu", () => {
			const text = $input.val() || "";
			const query = this.extractQuery(text);
			if (query === null) {
				if (state.open) close();
				return;
			}
			state.open = true;
			this.render(widget, $menu.find(".faco-slash-body"), query, state);
			$menu.show();
		});

		// --- Keydown handler (capture phase so it pre-empts Enter-send) ---
		$input[0].addEventListener(
			"keydown",
			(e) => {
				if (!state.open) return;
				if (e.key === "ArrowDown") {
					e.preventDefault();
					move(1);
				} else if (e.key === "ArrowUp") {
					e.preventDefault();
					move(-1);
				} else if (e.key === "Enter" && !e.shiftKey) {
					e.preventDefault();
					e.stopPropagation();
					pickActive();
				} else if (e.key === "Tab") {
					e.preventDefault();
					e.stopPropagation();
					pickActive();
				} else if (e.key === "Escape") {
					e.preventDefault();
					$input.val("").trigger("input");
					close();
				}
			},
			true
		);

		// Close on outside click
		const ns = "slashmenu-" + Math.random().toString(36).slice(2, 8);
		$(document).on("mousedown." + ns, (e) => {
			if (!state.open) return;
			if (!$menu[0].contains(e.target) && e.target !== $input[0]) {
				close();
			}
		});

		widget._slashMenuState = state;
	},

	/**
	 * Prefetch and cache templates on the widget instance.
	 * @param {Object} widget
	 */
	async prefetch(widget) {
		if (widget._templatesFetching) return widget._templatesFetching;
		widget._templatesFetching = (async () => {
			try {
				const response = await frappe.call({
					method: "frappe_assistant_core.chat.api.prompts.get_prompt_templates",
					type: "GET",
				});
				const data = response?.message || {};
				widget._templatesCache = {
					templates: Array.isArray(data.templates) ? data.templates : [],
					pinned: Array.isArray(data.pinned) ? data.pinned : [],
				};
			} catch (error) {
				widget._templatesCache = { templates: [], pinned: [] };
			}
			widget._templatesFetching = null;
		})();
		return widget._templatesFetching;
	},

	/**
	 * Return the query part after "/", or null if the input is not in slash mode.
	 * Slash must be at position 0 and the query must contain no whitespace.
	 */
	extractQuery(text) {
		if (!text || text[0] !== "/") return null;
		const after = text.slice(1);
		if (/\s/.test(after)) return null;
		return after;
	},

	/**
	 * Render pinned + all-templates sections, filtered by query.
	 */
	render(widget, $body, query, state) {
		const cache = widget._templatesCache || { templates: [], pinned: [] };
		const needle = (query || "").toLowerCase();

		const matches = (t) => {
			if (!needle) return true;
			return (
				(t.title || "").toLowerCase().includes(needle) ||
				(t.name || "").toLowerCase().includes(needle) ||
				(t.description || "").toLowerCase().includes(needle)
			);
		};

		const pinnedSet = new Set(cache.pinned);
		const pinned = cache.templates
			.filter((t) => pinnedSet.has(t.name) && matches(t))
			.slice(0, 5);
		const others = cache.templates
			.filter((t) => !pinnedSet.has(t.name) && matches(t))
			.slice(0, 8);

		$body.empty();
		state.rows = [];

		if (pinned.length > 0) {
			$body.append('<div class="faco-slash-section-label">Pinned</div>');
			pinned.forEach((t) =>
				state.rows.push({ template: t, element: this.appendRow($body, t) })
			);
		}

		if (others.length > 0) {
			$body.append('<div class="faco-slash-section-label">All templates</div>');
			others.forEach((t) =>
				state.rows.push({ template: t, element: this.appendRow($body, t) })
			);
		}

		if (state.rows.length === 0) {
			const q = this.escapeHtml(query || "…");
			$body.append(
				`<div class="faco-slash-empty">No templates match <code>${q}</code></div>`
			);
		}

		// Hover + click bindings
		state.rows.forEach((row, idx) => {
			row.element
				.on("mouseenter", () => {
					state.activeIndex = idx;
					this.highlight(state);
				})
				.on("mousedown", (e) => {
					e.preventDefault();
					this.pick(widget, row.template, widget.$widget.find(".faco-input"), () => {
						state.open = false;
						widget.$widget.find(".faco-slash-menu").hide();
					});
				});
		});

		// Reset highlight to first row
		state.activeIndex = 0;
		this.highlight(state);
	},

	appendRow($body, t) {
		const icon = this.CATEGORY_ICONS[t.category] || "📋";
		const title = this.escapeHtml(t.title || t.name || "");
		const desc = t.description ? this.escapeHtml(t.description) : "";
		const $row = $(`
			<div class="faco-slash-row" role="option">
				<span class="faco-slash-icon">${icon}</span>
				<span class="faco-slash-body-text">
					<span class="faco-slash-title">${title}</span>
					${desc ? `<span class="faco-slash-desc">${desc}</span>` : ""}
				</span>
				<span class="faco-slash-enter" aria-hidden="true">⏎</span>
			</div>
		`);
		$body.append($row);
		return $row;
	},

	highlight(state) {
		state.rows.forEach((row, idx) => {
			row.element.toggleClass("faco-slash-row-active", idx === state.activeIndex);
		});
		const active = state.rows[state.activeIndex];
		if (active && active.element[0] && active.element[0].scrollIntoView) {
			active.element[0].scrollIntoView({ block: "nearest" });
		}
	},

	/**
	 * Select a template: clear the `/query` from the input, then either open
	 * the arguments modal or render + send directly.
	 */
	async pick(widget, template, $input, close) {
		close();
		$input.val("").trigger("input");

		const args = Array.isArray(template.arguments) ? template.arguments : [];
		if (args.length > 0 && window.FACOWidgetTemplates) {
			window.FACOWidgetTemplates.show_template_argument_modal(widget, template);
			return;
		}

		// No arguments — render the prompt server-side, then send
		try {
			const rendered = await window.FACOWidgetTemplates.get_rendered_prompt(
				template.name,
				{}
			);
			if (rendered && rendered.prompt) {
				widget.send_message(rendered.prompt);
			} else {
				widget.send_message(template.description || template.title || template.name);
			}
		} catch (error) {
			widget.send_message(template.description || template.title || template.name);
		}
	},

	escapeHtml(s) {
		return String(s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");
	},
};
