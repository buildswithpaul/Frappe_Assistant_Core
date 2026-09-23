import { baseCall, friendlyError, getCall, getCsrfToken, networkError } from "../_core";

// ---------------------------------------------------------------------
// Listing → Template shape adapter
// ---------------------------------------------------------------------
// The marketplace app speaks "listings" (workflow / prompt / skill);
// existing FACO UI was built around "templates" (workflow only). Until
// the UI is generalized in chunk 4, we adapt the marketplace responses
// to look like the legacy template shape so callers (workflowStore,
// MarketplaceView, TemplateCard, etc.) keep rendering with no churn.
function listingToTemplate(listing) {
	if (!listing) return listing;
	return {
		// Identity — preserve listing.name as the canonical id
		name: listing.name,
		template_name: listing.title,
		// Display
		description: listing.description,
		short_description: listing.short_description,
		category: listing.category,
		tags: listing.tags,
		icon: listing.icon,
		// Ownership / moderation
		tenant: listing.tenant,
		creator_tenant: listing.creator_tenant,
		is_official: listing.is_official,
		is_public: listing.is_public,
		is_published: listing.is_published,
		review_status: listing.review_status,
		featured: listing.featured,
		// Stats
		import_count: listing.import_count,
		average_rating: listing.average_rating,
		rating_count: listing.rating_count,
		view_count: listing.view_count,
		last_published_at: listing.last_published_at,
		modified: listing.modified,
		// Source-record fields (when include_source=1)
		default_model_id: listing.source_summary?.default_model_id,
		min_agent_nodes: listing.source_summary?.min_agent_nodes,
		tool_hints: listing.source_summary?.tool_hints,
		// New fields the UI may want eventually
		listing_type: listing.listing_type,
		source_doctype: listing.source_doctype,
		source_name: listing.source_name,
		plan_tier: listing.plan_tier,
	};
}

function listingsToTemplatesPayload(payload) {
	if (!payload) return payload;
	return {
		templates: (payload.listings || []).map(listingToTemplate),
		total: payload.total ?? 0,
		page: payload.page ?? 0,
		page_size: payload.page_size ?? 20,
		marketplace_enabled: payload.marketplace_enabled,
	};
}

export const workflows = {
	list: (status = null, page = 0, pageSize = 20) =>
		getCall("frappe_assistant_core.chat.api.list_workflows", {
			status,
			page,
			page_size: pageSize,
		}),

	create: (
		workflowName,
		description = "",
		{ defaultModelId = null, defaultUserId = null, graphJson = null } = {}
	) =>
		baseCall("frappe_assistant_core.chat.api.create_workflow", {
			workflow_name: workflowName,
			description,
			default_model_id: defaultModelId,
			default_user_id: defaultUserId,
			graph_json: graphJson,
		}),

	get: (name = null, workflowName = null) =>
		getCall("frappe_assistant_core.chat.api.get_workflow", {
			name,
			workflow_name: workflowName,
		}),

	update: (name, updates = {}) =>
		baseCall("frappe_assistant_core.chat.api.update_workflow", {
			name,
			...updates,
		}),

	delete: (name) =>
		baseCall("frappe_assistant_core.chat.api.delete_workflow", {
			name,
		}),

	execute: (name, inputData = null, userId = null) =>
		baseCall("frappe_assistant_core.chat.api.execute_workflow", {
			name,
			input_data: inputData,
			user_id: userId,
		}),

	cancelRun: (runName) =>
		baseCall("frappe_assistant_core.chat.api.cancel_workflow_run", {
			run_name: runName,
		}),

	getRun: (runName) =>
		getCall("frappe_assistant_core.chat.api.get_workflow_run", {
			run_name: runName,
		}),

	listRuns: (workflowName = null, status = null, page = 0, pageSize = 20) =>
		getCall("frappe_assistant_core.chat.api.list_workflow_runs", {
			workflow_name: workflowName,
			status,
			page,
			page_size: pageSize,
		}),

	getAuditSummary: (workflowId, window = "last_7_days") =>
		getCall(
			"frappe_assistant_core.chat.api.get_workflow_audit_summary",
			{
				workflow_id: workflowId,
				window,
			}
		),

	setSchedule: (name, cronExpression, timezone = "UTC", enabled = true, defaultInput = null) =>
		baseCall("frappe_assistant_core.chat.api.set_workflow_schedule", {
			name,
			cron_expression: cronExpression,
			timezone,
			enabled,
			default_input: defaultInput,
		}),

	validateGraph: (graphJson) =>
		baseCall("frappe_assistant_core.chat.api.validate_workflow_graph", {
			graph_json: graphJson,
		}),

	testNode: (nodeJson, inputText = "Test input", defaultModelId = null, defaultUserId = null) =>
		baseCall("frappe_assistant_core.chat.api.test_workflow_node", {
			node_json: nodeJson,
			input_text: inputText,
			default_model_id: defaultModelId,
			default_user_id: defaultUserId,
		}),

	runNode: (name, nodeId, inputText = "Test input", userId = null) =>
		baseCall("frappe_assistant_core.chat.api.run_workflow_node", {
			name,
			node_id: nodeId,
			input_text: inputText,
			user_id: userId,
		}),

	// Event-trigger APIs
	triggers: {
		// Both keys travel: `workflow_docname` is the authoritative WF-#####
		// binding, `workflow_name` the legacy display-name column. Frappe drops
		// arguments a whitelisted function does not declare, so sending both is
		// safe on either side of the trigger-binding change.
		list: (workflowName = null, workflowDocname = null) =>
			getCall(
				"frappe_assistant_core.chat.api.workflow_triggers.list_triggers",
				{ workflow_name: workflowName, workflow_docname: workflowDocname }
			),

		create: (payload) =>
			baseCall(
				"frappe_assistant_core.chat.api.workflow_triggers.create_trigger",
				payload
			),

		update: (name, payload) =>
			baseCall(
				"frappe_assistant_core.chat.api.workflow_triggers.update_trigger",
				{ name, ...payload }
			),

		delete: (name) =>
			baseCall(
				"frappe_assistant_core.chat.api.workflow_triggers.delete_trigger",
				{ name }
			),

		toggle: (name, enabled) =>
			baseCall(
				"frappe_assistant_core.chat.api.workflow_triggers.toggle_trigger",
				{ name, enabled: enabled ? 1 : 0 }
			),

		listDoctypes: (search = null, limit = 50) =>
			getCall(
				"frappe_assistant_core.chat.api.workflow_triggers.list_filterable_doctypes",
				{ search, limit }
			),

		getDoctypeFields: (doctype) =>
			getCall(
				"frappe_assistant_core.chat.api.workflow_triggers.get_doctype_fields",
				{ doctype }
			),

		log: (triggerName, limit = 20) =>
			getCall(
				"frappe_assistant_core.chat.api.workflow_triggers.get_trigger_log",
				{ trigger_name: triggerName, limit }
			),

		test: (triggerName) =>
			baseCall(
				"frappe_assistant_core.chat.api.workflow_triggers.test_trigger",
				{ trigger_name: triggerName }
			),
	},

	// Template APIs — route through the marketplace app (chunk 3 rewire).
	// Response shapes are adapted to look like the legacy {templates, total}
	// surface so consumers (workflowStore.templates, MarketplaceView, etc.)
	// don't need to change. The native {listings, total} shape is available
	// directly via api.marketplace.* in the next iteration.
	listTemplates: async (
		category = null,
		search = null,
		sortBy = null,
		featuredOnly = false,
		minRating = null,
		page = 0,
		pageSize = 20
	) => {
		const payload = await getCall(
			"frappe_assistant_core.chat.api.list_listings",
			{
				listing_type: "Workflow",
				category,
				search,
				sort_by: sortBy,
				featured_only: featuredOnly ? 1 : 0,
				min_rating: minRating,
				page,
				page_size: pageSize,
			}
		);
		return listingsToTemplatesPayload(payload);
	},

	getTemplate: async (templateName = null, name = null) => {
		// Old API accepted either template_name or listing name; the new
		// marketplace lookup is by listing name only. When a caller passes
		// template_name, we look it up via list_listings (cheap — server
		// filters by source_name) and grab the first match.
		let listingName = name;
		if (!listingName && templateName) {
			const listings = await getCall(
				"frappe_assistant_core.chat.api.list_listings",
				{ listing_type: "Workflow", search: templateName, page: 0, page_size: 5 }
			);
			const match = (listings?.listings || []).find(
				(l) => l.title === templateName || l.source_name === templateName
			);
			if (!match) {
				throw new Error(`Template '${templateName}' not found in marketplace`);
			}
			listingName = match.name;
		}
		if (!listingName) {
			throw new Error("Either template_name or name is required");
		}
		const listing = await getCall(
			"frappe_assistant_core.chat.api.get_listing",
			{ name: listingName, include_source: "1" }
		);
		const tmpl = listingToTemplate(listing);
		// Inline the full source record (graph_json + variables_schema)
		// because the legacy callers expect it on the template object itself.
		if (listing?.source) {
			tmpl.graph_json = listing.source.graph_json;
			tmpl.variables_schema = listing.source.variables_schema;
			tmpl.default_variables = listing.source.default_variables;
			tmpl.error_strategy = listing.source.error_strategy;
			tmpl.timeout_seconds = listing.source.timeout_seconds;
			tmpl.suggested_cron = listing.source.suggested_cron;
			tmpl.suggested_timezone = listing.source.suggested_timezone;
			tmpl.suggested_input = listing.source.suggested_input;
			tmpl.required_tools = listing.source.required_tools;
			tmpl.required_tool_descriptions = listing.source.required_tool_descriptions;
			tmpl.author = listing.source.author;
			tmpl.version = listing.source.version;
		}
		// Plan-tier check result for upgrade UI
		tmpl.plan_tier_allowed = listing?.plan_tier_allowed;
		tmpl.plan_tier_reason = listing?.plan_tier_reason;
		return tmpl;
	},

	importTemplate: (
		templateNameOrListingName = null,
		workflowName = null,
		variables = null,
		defaultModelId = null
	) =>
		baseCall("frappe_assistant_core.chat.api.import_listing", {
			name: templateNameOrListingName,
			new_title: workflowName,
			variables,
			default_model_id: defaultModelId,
		}),

	// Publishing — workflow → listing (chunk 5)
	publishWorkflow: (
		workflowName,
		{
			templateName = null,
			category = "General",
			shortDescription = null,
			description = null,
			tags = null,
			isPublic = false,
			planTier = null,
		} = {}
	) =>
		baseCall("frappe_assistant_core.chat.api.publish_workflow", {
			workflow_name: workflowName,
			template_name: templateName,
			category,
			short_description: shortDescription,
			description,
			tags,
			is_public: isPublic ? "1" : "0",
			plan_tier: planTier,
		}),

	uploadTemplate: async (file, isPublic = false, isPublished = true) => {
		const formData = new FormData();
		formData.append("file", file);
		formData.append("is_public", isPublic ? "1" : "0");
		formData.append("is_published", isPublished ? "1" : "0");
		let response;
		try {
			response = await fetch(
				// Hits the marketplace upload endpoint via FACO's whitelisted wrapper.
				"/api/method/assistant_runtime_marketplace.api.publishing.upload_listing_from_json",
				{
					method: "POST",
					body: formData,
					headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
					credentials: "same-origin",
				}
			);
		} catch (cause) {
			throw networkError(cause);
		}
		if (!response.ok) {
			const body = await response.text();
			throw friendlyError(response, body);
		}
		const data = await response.json();
		return data.message || data;
	},

	rateTemplate: (name, rating, review = null) =>
		baseCall("frappe_assistant_core.chat.api.rate_listing", {
			listing: name,
			rating,
			review,
		}),

	downloadTemplate: (name) =>
		getCall("frappe_assistant_core.chat.api.download_listing_as_json", {
			name,
		}),

	// Tool resolution
	resolveWorkflowTools: (toolDirectives) =>
		baseCall("frappe_assistant_core.chat.api.resolve_workflow_tools", {
			tool_directives: toolDirectives,
		}),

	// Moderation — routes through marketplace endpoints
	reportTemplate: (name, reason, details = null) =>
		baseCall("frappe_assistant_core.chat.api.report_listing", {
			listing: name,
			reason,
			details,
		}),

	listPendingReviews: async (page = 0, pageSize = 20) => {
		const payload = await getCall(
			"frappe_assistant_core.chat.api.list_pending_reviews",
			{ page, page_size: pageSize }
		);
		return listingsToTemplatesPayload(payload);
	},

	approveTemplate: (name, notes = null) =>
		baseCall("frappe_assistant_core.chat.api.approve_listing", {
			listing: name,
			notes,
		}),

	rejectTemplate: (name, reason) =>
		baseCall("frappe_assistant_core.chat.api.reject_listing", {
			listing: name,
			notes: reason,
		}),

	// Creator economy — routes through marketplace endpoint, response shape adapted
	getCreatorStats: async () => {
		const stats = await getCall(
			"frappe_assistant_core.chat.api.get_creator_stats",
			{}
		);
		// Old shape exposed `templates_published`, `total_imports`, `weighted_average_rating`,
		// `total_credits_earned` — new endpoint already uses the same field names.
		return stats || {};
	},

	// Template updates — read from AR Marketplace Version
	checkTemplateUpdates: (name) =>
		getCall("frappe_assistant_core.chat.api.check_workflow_update", {
			name,
		}),

	checkAllTemplateUpdates: () =>
		getCall(
			"frappe_assistant_core.chat.api.check_all_workflow_updates",
			{}
		),
};
