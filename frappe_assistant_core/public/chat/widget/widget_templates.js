// Frappe Assistant Copilot - Widget Templates Module
// Parameter modal + rendered-prompt fetch shared by the slash menu.
//
// Rendering rules mirror the SPA's ParameterModal:
//   - `arg.enum` (array)            → <select> dropdown
//   - name suggests long text       → <textarea>
//   - `arg.type` in {number,integer,email,url} → typed <input>
//   - otherwise                     → plain <input type="text">
// Defaults, descriptions, and title-cased labels match the SPA.

window.FACOWidgetTemplates = {
	/**
	 * Open the parameter form for a template, collect values, render via AR, and send.
	 * @param {Object} widget - Widget instance
	 * @param {Object} template - Template object with arguments
	 */
	show_template_argument_modal(widget, template) {
		const args = Array.isArray(template.arguments) ? template.arguments : [];

		const formHtml = args
			.map((arg, index) => {
				const name = arg.name || `arg_${index}`;
				const required = arg.required !== false;
				const label = this.format_label(name);
				const desc = arg.description
					? `<p class="faco-arg-desc">${this.escape(arg.description)}</p>`
					: "";
				const placeholder = arg.default
					? `Default: ${this.escape(arg.default)}`
					: `Enter ${label.toLowerCase()}…`;

				return `
				<div class="faco-arg-field">
					<label for="faco-arg-${name}" class="faco-arg-label">
						${this.escape(label)}${required ? ' <span class="faco-arg-required">*</span>' : ""}
					</label>
					${desc}
					${this.field_html(arg, name, placeholder, required)}
				</div>
			`;
			})
			.join("");

		const title = this.escape(template.title || template.name || "Template");
		const subtitle = template.description
			? `<div class="faco-template-modal-description">${this.escape(
					template.description
			  )}</div>`
			: "";

		const $modal = $(`
			<div class="faco-template-modal">
				<div class="faco-template-modal-content">
					<div class="faco-template-modal-header">
						<div>
							<h4>${title}</h4>
							<p class="faco-template-modal-subtitle">Fill in the details</p>
						</div>
						<button class="faco-template-modal-close" type="button" aria-label="Close">&times;</button>
					</div>
					${subtitle}
					<form class="faco-template-form">
						<div class="faco-template-form-body">
							${formHtml || '<p class="faco-arg-empty">This template has no parameters.</p>'}
						</div>
						<div class="faco-template-modal-actions">
							<button type="button" class="faco-template-cancel">Cancel</button>
							<button type="submit" class="faco-template-submit">Use</button>
						</div>
					</form>
				</div>
			</div>
		`);

		// Pre-fill defaults
		args.forEach((arg, index) => {
			const name = arg.name || `arg_${index}`;
			if (arg.default !== undefined && arg.default !== null && arg.default !== "") {
				$modal.find(`#faco-arg-${name}`).val(arg.default);
			}
		});

		// Close handlers
		$modal
			.find(".faco-template-modal-close, .faco-template-cancel")
			.on("click", () => $modal.remove());
		$modal.on("click", (e) => {
			if ($(e.target).is(".faco-template-modal")) $modal.remove();
		});
		// Esc to close
		$modal.on("keydown", (e) => {
			if (e.key === "Escape") {
				e.preventDefault();
				$modal.remove();
			}
		});

		// Submit
		$modal.find(".faco-template-form").on("submit", async (e) => {
			e.preventDefault();

			const values = {};
			args.forEach((arg, index) => {
				const name = arg.name || `arg_${index}`;
				const raw = $modal.find(`#faco-arg-${name}`).val();
				if (raw !== "" && raw !== null && raw !== undefined) {
					values[name] = raw;
				}
			});

			$modal.remove();

			try {
				const response = await frappe.call({
					method: "frappe_assistant_core.chat.api.prompts.get_rendered_prompt",
					type: "GET",
					args: {
						prompt_name: template.name,
						arguments: JSON.stringify(values),
					},
				});

				if (response.message && response.message.prompt) {
					widget.send_message(response.message.prompt);
				} else {
					widget.send_message(this.fallback_prompt(template, values));
				}
			} catch (error) {
				FACOLogger.error("Failed to render template:", error);
				widget.send_message(this.fallback_prompt(template, values));
			}
		});

		// Append to <body> so the modal covers the full viewport regardless of the
		// widget's size/position. Mirrors the SPA's <Teleport to="body"> pattern.
		$("body").append($modal);
		$modal.find("input, select, textarea").first().focus();
	},

	/**
	 * Build the appropriate form field for an argument.
	 */
	field_html(arg, name, placeholder, required) {
		// Enum → select
		if (Array.isArray(arg.enum) && arg.enum.length > 0) {
			const options = arg.enum
				.map((opt) => `<option value="${this.escape(opt)}">${this.escape(opt)}</option>`)
				.join("");
			return `
				<select id="faco-arg-${name}" name="${name}" class="faco-arg-input faco-arg-select" ${
				required ? "required" : ""
			}>
					<option value="" disabled ${arg.default ? "" : "selected"}>Select an option…</option>
					${options}
				</select>
			`;
		}

		// Long text → textarea
		if (this.is_long_text(name)) {
			return `
				<textarea id="faco-arg-${name}" name="${name}" class="faco-arg-input faco-arg-textarea"
					placeholder="${this.escape(placeholder)}" rows="3" ${required ? "required" : ""}></textarea>
			`;
		}

		// Typed input (number, email, url) → plain text
		const type = this.input_type(arg);
		return `
			<input id="faco-arg-${name}" name="${name}" type="${type}" class="faco-arg-input"
				placeholder="${this.escape(placeholder)}" ${required ? "required" : ""}>
		`;
	},

	/**
	 * Fetch a rendered prompt from the backend.
	 * @param {string} promptName
	 * @param {Object} args
	 * @returns {Promise<Object|null>}
	 */
	async get_rendered_prompt(promptName, args) {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.prompts.get_rendered_prompt",
				type: "GET",
				args: {
					prompt_name: promptName,
					arguments: JSON.stringify(args || {}),
				},
			});
			return response.message;
		} catch (error) {
			FACOLogger.error("Error rendering prompt:", error);
			return null;
		}
	},

	// --- helpers ---

	format_label(name) {
		if (!name) return "";
		return name
			.replace(/[_-]/g, " ")
			.split(" ")
			.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
			.join(" ");
	},

	is_long_text(name) {
		const n = (name || "").toLowerCase();
		return (
			n.includes("description") ||
			n.includes("content") ||
			n.includes("message") ||
			n.includes("text") ||
			n.includes("body")
		);
	},

	input_type(arg) {
		if (arg.type === "number" || arg.type === "integer") return "number";
		if (arg.type === "email") return "email";
		if (arg.type === "url") return "url";
		return "text";
	},

	fallback_prompt(template, values) {
		let prompt = template.description || template.title || template.name;
		Object.entries(values).forEach(([k, v]) => {
			if (v) prompt += ` (${k}: ${v})`;
		});
		return prompt;
	},

	escape(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");
	},
};
