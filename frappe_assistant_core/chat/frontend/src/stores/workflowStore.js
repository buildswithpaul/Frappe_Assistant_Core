import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

// Every status a run can end in. Cancelled and Timed Out are terminal too —
// treating only Completed/Failed as "done" leaves the toolbar spinning.
const TERMINAL_RUN_STATUSES = new Set(["Completed", "Failed", "Cancelled", "Timed Out"]);

const RUN_POLL_INTERVAL_MS = 2000;
// A run that never reports a terminal status must not poll a forgotten tab
// forever. The engine's own ceiling is timeout_seconds; this is the backstop.
const RUN_POLL_MAX_MS = 30 * 60 * 1000;

export const useWorkflowStore = defineStore("workflows", () => {
	// List state
	const workflows = ref([]);
	const isLoading = ref(false);
	const error = ref(null);
	const total = ref(0);
	const currentPage = ref(0);
	const pageSize = ref(20);
	const statusFilter = ref(null);

	// Current workflow (builder)
	const currentWorkflow = ref(null);
	const isDirty = ref(false);
	const isSaving = ref(false);
	const lastSavedGraphJson = ref(null);

	// Runs state
	const runs = ref([]);
	const currentRun = ref(null);
	const runsTotal = ref(0);
	const isRunning = ref(false);
	const isCancelling = ref(false);
	const activeRunName = ref(null);

	// The run poller lives here, not in a panel: its lifetime tracks the RUN.
	// Owned by a component, closing that component stranded isRunning at true
	// and left the toolbar disabled for the rest of the session.
	let pollTimer = null;
	let pollStartedAt = 0;

	// Cached data for config panel
	const availableModels = ref([]);
	const modelsError = ref(null);
	const availableMCPServers = ref([]);
	const availableTools = ref([]);
	// The raw list_user_tools envelope. The tool array alone cannot tell an
	// empty toolbox apart from an expired token, so the config panel needs it.
	const toolsResult = ref(null);
	const isLoadingTools = ref(false);

	// Template state
	const templates = ref([]);
	const templatesTotal = ref(0);
	const isLoadingTemplates = ref(false);
	const selectedTemplate = ref(null);

	// Creator economy state
	const creatorStats = ref(null);
	const isLoadingCreatorStats = ref(false);

	// Template update state
	const templateUpdates = ref([]);

	// Getters
	const hasWorkflows = computed(() => workflows.value.length > 0);

	// Actions
	async function loadWorkflows(status = null, page = 0) {
		isLoading.value = true;
		error.value = null;
		try {
			const result = await api.workflows.list(status, page, pageSize.value);
			workflows.value = result.workflows || [];
			total.value = result.total || 0;
			currentPage.value = result.page || 0;
			statusFilter.value = status;
		} catch (err) {
			error.value = err.message;
			logger.error("Failed to load workflows:", err);
		} finally {
			isLoading.value = false;
		}
	}

	async function createWorkflow(
		name,
		description = "",
		{ defaultUserId = null, defaultModelId = null, graphJson = null } = {}
	) {
		try {
			const result = await api.workflows.create(name, description, {
				defaultModelId,
				defaultUserId,
				graphJson,
			});
			// Reload list to include the new workflow
			await loadWorkflows(statusFilter.value, currentPage.value);
			return result;
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	async function loadWorkflow(name) {
		isLoading.value = true;
		error.value = null;
		try {
			const result = await api.workflows.get(name);
			currentWorkflow.value = result;
			lastSavedGraphJson.value = result.graph_json || null;
			isDirty.value = false;
			return result;
		} catch (err) {
			error.value = err.message;
			throw err;
		} finally {
			isLoading.value = false;
		}
	}

	async function saveWorkflow(name, updates) {
		isSaving.value = true;
		try {
			const result = await api.workflows.update(name, updates);
			if (updates.graph_json) {
				lastSavedGraphJson.value = updates.graph_json;
			}
			// Merge sent updates + backend response into currentWorkflow
			// (updates first to keep graph_json current; result second for server-authoritative fields)
			if (currentWorkflow.value && currentWorkflow.value.name === name) {
				Object.assign(currentWorkflow.value, updates, result);
			}
			isDirty.value = false;
			return result;
		} catch (err) {
			error.value = err.message;
			throw err;
		} finally {
			isSaving.value = false;
		}
	}

	async function deleteWorkflow(name) {
		try {
			await api.workflows.delete(name);
			workflows.value = workflows.value.filter((w) => w.name !== name);
			total.value = Math.max(0, total.value - 1);
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	async function executeWorkflow(name, inputData = null) {
		isRunning.value = true;
		try {
			const result = await api.workflows.execute(name, inputData);
			activeRunName.value = result.run_name || null;
			if (activeRunName.value) startRunPolling(activeRunName.value);
			return result;
		} catch (err) {
			error.value = err.message;
			isRunning.value = false;
			throw err;
		}
	}

	function startRunPolling(runName) {
		stopRunPolling();
		if (!runName) return;
		pollStartedAt = Date.now();
		pollTimer = setInterval(async () => {
			if (!activeRunName.value) {
				stopRunPolling();
				return;
			}
			if (Date.now() - pollStartedAt > RUN_POLL_MAX_MS) {
				stopRunPolling();
				isRunning.value = false;
				isCancelling.value = false;
				activeRunName.value = null;
				return;
			}
			try {
				await loadRun(activeRunName.value);
			} catch {
				// A transient poll failure is not a run failure — keep polling.
			}
		}, RUN_POLL_INTERVAL_MS);
	}

	function stopRunPolling() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	async function loadRuns(workflowName = null, status = null, page = 0) {
		try {
			const result = await api.workflows.listRuns(workflowName, status, page, 20);
			runs.value = result.runs || [];
			runsTotal.value = result.total || 0;
			return result;
		} catch (err) {
			logger.error("Failed to load runs:", err);
			return { runs: [], total: 0 };
		}
	}

	async function loadRun(runName) {
		try {
			const result = await api.workflows.getRun(runName);
			currentRun.value = result;
			// Only the ACTIVE run can end the run state. Expanding a finished
			// run in the history panel must not stop the live poller.
			if (
				runName === activeRunName.value &&
				result.status &&
				TERMINAL_RUN_STATUSES.has(result.status)
			) {
				isRunning.value = false;
				isCancelling.value = false;
				activeRunName.value = null;
				stopRunPolling();
			}
			return result;
		} catch (err) {
			logger.error("Failed to load run:", err);
			throw err;
		}
	}

	/**
	 * Ask the engine to stop. Cancellation is cooperative — the worker finishes
	 * the node it is on — so the run stays "active" here until a poll sees a
	 * terminal status. Credits already spent stay spent.
	 */
	async function cancelRun(runName) {
		isCancelling.value = true;
		try {
			const result = await api.workflows.cancelRun(runName);
			if (activeRunName.value === runName) await loadRun(runName).catch(() => {});
			return result;
		} catch (err) {
			isCancelling.value = false;
			error.value = err.message;
			throw err;
		}
	}

	async function setSchedule(
		name,
		cronExpression,
		timezone = "UTC",
		enabled = true,
		defaultInput = null
	) {
		try {
			return await api.workflows.setSchedule(
				name,
				cronExpression,
				timezone,
				enabled,
				defaultInput
			);
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	async function validateGraph(graphJson) {
		try {
			return await api.workflows.validateGraph(graphJson);
		} catch (err) {
			return { valid: false, error: err.message };
		}
	}

	async function testNode(nodeJson, inputText = "Test input", modelId = null, userId = null) {
		try {
			return await api.workflows.testNode(nodeJson, inputText, modelId, userId);
		} catch (err) {
			return { status: "Failed", error_message: err.message };
		}
	}

	async function runNode(workflowName, nodeId, inputText = "Test input", userId = null) {
		try {
			return await api.workflows.runNode(workflowName, nodeId, inputText, userId);
		} catch (err) {
			return { status: "Failed", error_message: err.message };
		}
	}

	async function loadModels() {
		try {
			const result = await api.models.getAvailable();
			// The terms gate answers with {error, error_code} instead of a model
			// list. Falling back to `result` here iterated that error object as
			// if it were models.
			if (Array.isArray(result?.models)) {
				availableModels.value = result.models;
				modelsError.value = null;
			} else {
				availableModels.value = [];
				modelsError.value = result?.error || "Models are unavailable right now.";
			}
		} catch (err) {
			logger.error("Failed to load models:", err);
			availableModels.value = [];
			modelsError.value = err.message || "Failed to load models";
		}
	}

	async function loadMCPServers() {
		try {
			const result = await api.user.getMCPServers();
			availableMCPServers.value = result?.mcp_servers || [];
		} catch (err) {
			logger.error("Failed to load MCP servers:", err);
		}
	}

	async function loadTools() {
		if (isLoadingTools.value) return;
		isLoadingTools.value = true;
		try {
			const result = await api.user.listTools();
			toolsResult.value = result || null;
			if (result?.success) {
				availableTools.value = result.tools || [];
				// Derive MCP servers from tools for backward compat
				const serverNames = [...new Set(availableTools.value.map((t) => t.server))];
				availableMCPServers.value = serverNames.map((name) => ({
					server_name: name,
					status: "Active",
				}));
			} else {
				availableTools.value = [];
			}
		} catch (err) {
			logger.error("Failed to load tools:", err);
			availableTools.value = [];
			toolsResult.value = { success: false, tools: [], errors: err.message };
		} finally {
			isLoadingTools.value = false;
		}
	}

	async function loadTemplates(
		category = null,
		search = null,
		sortBy = null,
		page = 0,
		{ featuredOnly = false, minRating = null, pageSize: ps = 20, append = false } = {}
	) {
		isLoadingTemplates.value = true;
		try {
			const result = await api.workflows.listTemplates(
				category,
				search,
				sortBy,
				featuredOnly,
				minRating,
				page,
				ps
			);
			if (append) {
				templates.value = [...templates.value, ...(result.templates || [])];
			} else {
				templates.value = result.templates || [];
			}
			templatesTotal.value = result.total || 0;
		} catch (err) {
			logger.error("Failed to load templates:", err);
			if (!append) templates.value = [];
		} finally {
			isLoadingTemplates.value = false;
		}
	}

	async function loadTemplate(templateName) {
		try {
			const result = await api.workflows.getTemplate(templateName);
			selectedTemplate.value = result;
			return result;
		} catch (err) {
			logger.error("Failed to load template:", err);
			throw err;
		}
	}

	async function importTemplate(
		templateName,
		workflowName = null,
		variables = null,
		defaultModelId = null
	) {
		try {
			const result = await api.workflows.importTemplate(
				templateName,
				workflowName,
				variables,
				defaultModelId
			);
			await loadWorkflows(statusFilter.value, currentPage.value);
			return result;
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	async function exportWorkflow(
		name,
		templateName = null,
		category = "General",
		saveAsTemplate = false,
		{
			shortDescription = null,
			description = null,
			tags = null,
			isPublic = false,
			planTier = null,
		} = {}
	) {
		// chunk 5: when saveAsTemplate is True we hit the marketplace
		// publish endpoint (which creates the template + a listing wrapping
		// it). When False we don't have a download-only path on the workflows
		// app anymore — the new equivalent is downloadTemplate(name) on a
		// listing, which the UI invokes after publishing.
		try {
			if (!saveAsTemplate) {
				throw new Error(
					"Download-only export was removed in the marketplace extraction. " +
						"Use publishWorkflow followed by downloadTemplate(listing_name)."
				);
			}
			return await api.workflows.publishWorkflow(name, {
				templateName,
				category,
				shortDescription,
				description,
				tags,
				isPublic,
				planTier,
			});
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	async function uploadTemplate(file, isPublic = false, isPublished = true) {
		try {
			return await api.workflows.uploadTemplate(file, isPublic, isPublished);
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	async function rateTemplate(name, rating, review = null) {
		try {
			return await api.workflows.rateTemplate(name, rating, review);
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	async function downloadTemplate(name) {
		try {
			const data = await api.workflows.downloadTemplate(name);
			// Trigger browser download
			const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = `${data.template_name || "template"}.json`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			return data;
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	// Moderation actions
	async function reportTemplate(name, reason, details = null) {
		try {
			return await api.workflows.reportTemplate(name, reason, details);
		} catch (err) {
			error.value = err.message;
			throw err;
		}
	}

	// Creator economy actions
	async function loadCreatorStats() {
		if (isLoadingCreatorStats.value) return;
		isLoadingCreatorStats.value = true;
		try {
			creatorStats.value = await api.workflows.getCreatorStats();
		} catch (err) {
			logger.error("Failed to load creator stats:", err);
		} finally {
			isLoadingCreatorStats.value = false;
		}
	}

	// Template update actions
	async function checkAllTemplateUpdates() {
		try {
			const result = await api.workflows.checkAllTemplateUpdates();
			templateUpdates.value = result?.updates || [];
		} catch (err) {
			logger.error("Failed to check template updates:", err);
		}
	}

	function getUpdateForWorkflow(workflowName) {
		return templateUpdates.value.find((u) => u.workflow_name === workflowName);
	}

	function markDirty() {
		isDirty.value = true;
	}

	function markClean() {
		isDirty.value = false;
	}

	function clearCurrentWorkflow() {
		stopRunPolling();
		currentWorkflow.value = null;
		isDirty.value = false;
		lastSavedGraphJson.value = null;
		currentRun.value = null;
		isRunning.value = false;
		isCancelling.value = false;
		activeRunName.value = null;
	}

	/**
	 * Copy a workflow: same graph and execution settings, a new name.
	 * The server deduplicates the name, so "(copy)" may come back as "(copy) (2)".
	 */
	async function duplicateWorkflow(name) {
		const source = await api.workflows.get(name);
		const created = await api.workflows.create(
			`${source.workflow_name || name} (copy)`,
			source.description || "",
			{
				defaultModelId: source.default_model_id || null,
				defaultUserId: source.default_user_id || null,
				graphJson: source.graph_json || null,
			}
		);
		if (created?.name) {
			const settings = {};
			if (source.error_strategy) settings.error_strategy = source.error_strategy;
			if (source.timeout_seconds) settings.timeout_seconds = source.timeout_seconds;
			if (source.max_retries) settings.max_retries = source.max_retries;
			if (source.max_node_executions)
				settings.max_node_executions = source.max_node_executions;
			if (Object.keys(settings).length) {
				await api.workflows.update(created.name, settings);
			}
		}
		await loadWorkflows(statusFilter.value, currentPage.value);
		return created;
	}

	// Handle realtime progress events
	function handleRunProgress(data) {
		if (!currentRun.value) return;

		if (
			data.type === "node_started" ||
			data.type === "node_completed" ||
			data.type === "node_failed"
		) {
			// Update current run's node_runs
			if (currentRun.value.node_runs) {
				const existing = currentRun.value.node_runs.find(
					(n) => n.node_id === data.node_id
				);
				if (existing) {
					Object.assign(existing, data);
				} else {
					currentRun.value.node_runs.push(data);
				}
			}
			if (data.type === "node_started") {
				currentRun.value.current_node = data.node_id;
			}
			if (data.type === "node_completed") {
				currentRun.value.completed_nodes = (currentRun.value.completed_nodes || 0) + 1;
			}
		}

		if (data.type === "run_completed" || data.type === "run_failed") {
			currentRun.value.status = data.type === "run_completed" ? "Completed" : "Failed";
			isRunning.value = false;
			isCancelling.value = false;
			activeRunName.value = null;
			stopRunPolling();
		}
	}

	return {
		// List state
		workflows,
		isLoading,
		error,
		total,
		currentPage,
		pageSize,
		statusFilter,

		// Builder state
		currentWorkflow,
		isDirty,
		isSaving,
		lastSavedGraphJson,

		// Run state
		runs,
		currentRun,
		runsTotal,
		isRunning,
		isCancelling,
		activeRunName,

		// Config data
		availableModels,
		modelsError,
		availableMCPServers,
		availableTools,
		toolsResult,
		isLoadingTools,

		// Template state
		templates,
		templatesTotal,
		isLoadingTemplates,
		selectedTemplate,

		// Creator economy state
		creatorStats,
		isLoadingCreatorStats,

		// Template update state
		templateUpdates,

		// Getters
		hasWorkflows,

		// Actions
		loadWorkflows,
		createWorkflow,
		loadWorkflow,
		saveWorkflow,
		deleteWorkflow,
		duplicateWorkflow,
		executeWorkflow,
		loadRuns,
		loadRun,
		startRunPolling,
		stopRunPolling,
		cancelRun,
		setSchedule,
		validateGraph,
		testNode,
		runNode,
		loadModels,
		loadMCPServers,
		loadTools,
		loadTemplates,
		loadTemplate,
		importTemplate,
		exportWorkflow,
		uploadTemplate,
		rateTemplate,
		downloadTemplate,
		reportTemplate,
		loadCreatorStats,
		checkAllTemplateUpdates,
		getUpdateForWorkflow,
		markDirty,
		markClean,
		clearCurrentWorkflow,
		handleRunProgress,
	};
});
