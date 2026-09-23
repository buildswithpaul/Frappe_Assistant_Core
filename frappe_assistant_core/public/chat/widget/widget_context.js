// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Context Module
// Handles context detection and DOM content extraction for the FACO widget

/**
 * Widget Context Module
 * Responsible for detecting page context and extracting screen content
 */
window.FACOWidgetContext = {
	/**
	 * Detect and build context object from current page
	 * @returns {Object} Context object with page type and metadata
	 */
	detect_context() {
		const route = frappe.get_route();

		if (route && route[0] === "Form" && window.cur_frm && cur_frm.doc) {
			return {
				type: "Form",
				doctype: cur_frm.doctype,
				name: cur_frm.doc.name,
				url: window.location.href,
				is_new: cur_frm.is_new(),
			};
		}

		if (route && route[0] === "List") {
			return {
				type: "List",
				doctype: route[1],
				url: window.location.href,
				has_list_view: window.cur_list ? true : false,
			};
		}

		if (route && route[0] === "query-report") {
			return {
				type: "Report",
				name: route[1],
				url: window.location.href,
			};
		}

		if (route && route[0] === "Tree" && route[1]) {
			return {
				type: "Tree",
				doctype: route[1],
				url: window.location.href,
			};
		}

		if (
			route &&
			(route[0] === "Workspaces" || route.length === 0 || route[0] === "workspace")
		) {
			return {
				type: "Workspace",
				workspace_name: route[1] || "Home",
				url: window.location.href,
			};
		}

		if (route && route[0] === "dashboard") {
			return {
				type: "Dashboard",
				dashboard_name: route[1],
				url: window.location.href,
			};
		}

		if (route && route[0] === "print") {
			return {
				type: "Print",
				doctype: route[1],
				name: route[2],
				print_format: route[3],
				url: window.location.href,
			};
		}

		if (route && frappe.pages && frappe.pages[route[0]]) {
			return {
				type: "Custom Page",
				page_name: route[0],
				url: window.location.href,
			};
		}

		if (window.cur_page && window.cur_page.page) {
			const page_name = window.cur_page.page.page_name || route[0] || "Unknown";
			return {
				type: "Page",
				page_name: page_name,
				url: window.location.href,
			};
		}

		// General/Unknown page
		return {
			type: "General",
			route: route,
			url: window.location.href,
			page_title: document.title,
		};
	},

	/**
	 * Get context display text for UI indicator
	 * @param {Object} context - Context object
	 * @returns {string|null} Display text or null if no display needed
	 */
	get_context_display_text(context) {
		if (!context || context.type === "General") {
			return null;
		}

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
				return null;
		}
	},

	/**
	 * Extract visible content from the page DOM
	 * @param {Object} context - Current page context
	 * @param {Object} settings - Widget settings (for privacy options)
	 * @returns {string} Formatted content string for LLM
	 */
	async extract_screen_content(context, settings) {
		try {
			// Check if DOM extraction is enabled (privacy setting)
			const enable_dom = settings?.privacy?.enable_dom_extraction !== false;
			if (!enable_dom) {
				return this.extract_fallback_content(context);
			}

			let content = {
				page_title: document.title,
				page_type: context.type,
				text_content: "",
				structured_data: {},
			};

			// Get the main page container (excluding the widget itself)
			const $page = $(".page-content, .layout-main, .page-container").first();
			if (!$page.length) {
				return this.extract_fallback_content(context);
			}

			// Extract page title/heading
			const $pageTitle = $page.find(".page-title, h1, h2").first();
			if ($pageTitle.length) {
				content.page_heading = $pageTitle.text().trim();
			}

			// Type-specific extraction
			if (context.type === "Form" && window.cur_frm) {
				content.structured_data = this.extract_form_dom();
			} else if (context.type === "List" && window.cur_list) {
				content.structured_data = this.extract_list_dom(context);
			} else if (context.type === "Report" && frappe.query_report) {
				content.structured_data = this.extract_report_dom(context);
			} else if (context.type === "Workspace") {
				content.structured_data = this.extract_workspace_dom(context);
			} else if (context.type === "Dashboard") {
				content.structured_data = this.extract_dashboard_dom(context);
			} else {
				content.structured_data = this.extract_generic_dom($page);
			}

			// Extract visible text content (cleaned)
			content.text_content = this.extract_visible_text($page);

			// Format as human-readable string
			return this.format_extracted_content(content);
		} catch (error) {
			FACOLogger.error("Error extracting screen content:", error);
			return this.extract_fallback_content(context);
		}
	},

	/**
	 * Extract form data from cur_frm
	 * @returns {Object} Form data
	 */
	extract_form_dom() {
		if (!window.cur_frm) return {};

		const doc = cur_frm.doc;
		const meta = cur_frm.meta;
		const data = {
			doctype: cur_frm.doctype,
			name: doc.name,
			docstatus: doc.docstatus,
			fields: {},
		};

		// Get visible fields with values
		meta.fields.forEach((field) => {
			if (field.fieldtype === "Section Break" || field.fieldtype === "Column Break") return;

			const value = doc[field.fieldname];
			if (value !== null && value !== undefined && value !== "") {
				if (field.fieldtype === "Table") {
					data.fields[field.label] = `${(value || []).length} rows`;
				} else {
					data.fields[field.label] = value;
				}
			}
		});

		return data;
	},

	/**
	 * Extract list view data from DOM
	 * @param {Object} context - Current context
	 * @returns {Object} List data
	 */
	extract_list_dom(context) {
		const data = {
			doctype: context.doctype,
			visible_records: [],
		};

		$(".list-row")
			.slice(0, 10)
			.each((i, row) => {
				const $row = $(row);
				const record = {};

				const subject = $row.find(".level-item.bold, .list-subject").text().trim();
				if (subject) record.title = subject;

				$row.find(".ellipsis").each((j, field) => {
					const text = $(field).text().trim();
					if (text && text !== subject) {
						record[`field_${j}`] = text;
					}
				});

				if (Object.keys(record).length > 0) {
					data.visible_records.push(record);
				}
			});

		return data;
	},

	/**
	 * Extract report data including filters and visible results
	 * @param {Object} context - Current context
	 * @returns {Object} Report data
	 */
	extract_report_dom(context) {
		const data = {
			report_name: context.name,
			filters: {},
			columns: [],
			sample_data: [],
		};

		if (frappe.query_report && frappe.query_report.get_values) {
			data.filters = frappe.query_report.get_values();
		}

		$(".dt-header .dt-cell")
			.slice(0, 10)
			.each((i, cell) => {
				const colName = $(cell).text().trim();
				if (colName) data.columns.push(colName);
			});

		$(".dt-row")
			.slice(0, 5)
			.each((i, row) => {
				const rowData = {};
				$(row)
					.find(".dt-cell")
					.each((j, cell) => {
						if (data.columns[j]) {
							rowData[data.columns[j]] = $(cell).text().trim();
						}
					});
				if (Object.keys(rowData).length > 0) {
					data.sample_data.push(rowData);
				}
			});

		return data;
	},

	/**
	 * Extract workspace shortcuts and links
	 * @param {Object} context - Current context
	 * @returns {Object} Workspace data
	 */
	extract_workspace_dom(context) {
		const data = {
			workspace_name: context.workspace_name,
			shortcuts: [],
			links: [],
		};

		$(".shortcut-widget-box")
			.slice(0, 10)
			.each((i, shortcut) => {
				const $shortcut = $(shortcut);
				const label = $shortcut.find(".widget-head").text().trim();
				const count = $shortcut.find(".widget-body").text().trim();
				if (label) {
					data.shortcuts.push({ label, count });
				}
			});

		$(".desk-card, .widget-group-head")
			.slice(0, 15)
			.each((i, card) => {
				const label = $(card).text().trim();
				if (label && label.length < 100) {
					data.links.push(label);
				}
			});

		return data;
	},

	/**
	 * Extract dashboard charts and data
	 * @param {Object} context - Current context
	 * @returns {Object} Dashboard data
	 */
	extract_dashboard_dom(context) {
		const data = {
			dashboard_name: context.dashboard_name,
			charts: [],
		};

		$(".dashboard-chart-container, .chart-container")
			.slice(0, 10)
			.each((i, chart) => {
				const $chart = $(chart);
				const title = $chart.find(".chart-title, .dashboard-chart-title").text().trim();
				if (title && title.length < 100) {
					data.charts.push(title);
				}
			});

		return data;
	},

	/**
	 * Generic extraction for any page - find key elements
	 * @param {jQuery} $page - Page jQuery element
	 * @returns {Object} Generic page data
	 */
	extract_generic_dom($page) {
		const data = {
			headings: [],
			buttons: [],
			key_info: [],
		};

		$page
			.find("h1, h2, h3")
			.slice(0, 10)
			.each((i, h) => {
				const text = $(h).text().trim();
				if (text && text.length < 200) {
					data.headings.push(text);
				}
			});

		$page
			.find("button.btn-primary, button.btn-default")
			.slice(0, 10)
			.each((i, btn) => {
				const text = $(btn).text().trim();
				if (text && text.length < 50) {
					data.buttons.push(text);
				}
			});

		$page
			.find(".form-group, .data-row")
			.slice(0, 20)
			.each((i, group) => {
				const $group = $(group);
				const label = $group.find("label, .label").first().text().trim();
				const value =
					$group.find("input, select, .value, .control-value").first().val() ||
					$group.find(".value, .control-value").first().text().trim();

				if (label && value && value.length < 200) {
					data.key_info.push({ label, value });
				}
			});

		return data;
	},

	/**
	 * Extract clean visible text from page
	 * @param {jQuery} $page - Page jQuery element
	 * @returns {string} Cleaned text content
	 */
	extract_visible_text($page) {
		const $clone = $page.clone();
		$clone.find("script, style, .faco-widget, .navbar, .sidebar, .dropdown-menu").remove();

		let text = $clone.text();
		text = text.replace(/\s+/g, " ").trim();

		if (text.length > 3000) {
			text = text.substring(0, 3000) + "...";
		}

		return text;
	},

	/**
	 * Format extracted content as human-readable text for LLM
	 * @param {Object} content - Extracted content object
	 * @returns {string} Formatted string
	 */
	format_extracted_content(content) {
		let formatted = `Page: ${content.page_heading || content.page_title}\n`;
		formatted += `Type: ${content.page_type}\n\n`;

		if (content.structured_data && Object.keys(content.structured_data).length > 0) {
			const structured_json = JSON.stringify(content.structured_data, null, 2);

			if (structured_json.length > 2000) {
				formatted += `Structured Data:\n`;
				formatted += structured_json.substring(0, 2000) + "\n...[truncated]\n\n";
			} else {
				formatted += `Structured Data:\n`;
				formatted += structured_json;
				formatted += `\n\n`;
			}
		}

		if (content.text_content && content.text_content.length > 50) {
			formatted += `Visible Text:\n${content.text_content}\n`;
		}

		if (formatted.length > 5000) {
			formatted =
				formatted.substring(0, 5000) +
				"\n\n...[Content truncated to stay within token limits]";
		}

		return formatted;
	},

	/**
	 * Fallback when extraction fails
	 * @param {Object} context - Current context
	 * @returns {string} Basic fallback content
	 */
	extract_fallback_content(context) {
		return `Page: ${document.title}\nType: ${context.type}\nURL: ${window.location.href}`;
	},
};
