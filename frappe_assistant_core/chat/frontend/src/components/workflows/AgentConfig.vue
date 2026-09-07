<template>
	<div class="agent-config">
		<PromptEditor
			:model-value="config.system_prompt || ''"
			:variables="variables"
			:directives="configuredTools"
			:resolution="resolution"
			:readonly="readonly"
			@update:model-value="updatePrompt"
		/>

		<div class="config-section">
			<label class="config-label">Model</label>
			<select
				v-model="config.model_id"
				class="config-input config-select"
				:disabled="readonly"
				@change="emitUpdate"
			>
				<option value="">Workflow default</option>
				<optgroup v-for="group in modelGroups" :key="group.tier" :label="group.tier">
					<option v-for="m in group.models" :key="m.model_id" :value="m.model_id">
						{{ m.display_name || m.model_id }}
					</option>
				</optgroup>
			</select>
			<p v-if="modelsError" class="config-hint error">{{ modelsError }}</p>
		</div>

		<ToolSection
			:directives="configuredTools"
			:all-tools="allTools"
			:is-loading-tools="isLoadingTools"
			:resolution="resolution"
			:is-resolving="isResolving"
			:discovery-state="discoveryState"
			:tools-result="toolsResult"
			:runtime-user-label="runtimeUserLabel"
			:readonly="readonly"
			@add="addTool"
			@remove="removeTool"
			@toggle-priority="togglePriority"
			@toggle-required="setRequired"
			@recheck="resolveTools"
			@reload-tools="reloadTools"
		/>

		<div class="config-section">
			<label class="config-check-label">
				<input
					type="checkbox"
					:checked="!!config.use_memory"
					:disabled="readonly"
					@change="setUseMemory($event.target.checked)"
				/>
				<span>Use team instructions and memories</span>
			</label>
			<p class="config-hint">
				Injects the team's instructions and this agent user's memories ahead of the prompt,
				the same context a chat message gets.
			</p>
		</div>

		<div class="config-section">
			<label class="config-label"
				>User ID Override <span class="optional">(optional)</span></label
			>
			<input
				v-model="config.user_id"
				class="config-input"
				placeholder="Leave blank to use the agent's default user"
				:readonly="readonly"
				@input="emitUpdate"
			/>
			<p class="config-hint">
				Whose MCP tools this task uses. Blank falls back to the agent's "Runs as" user.
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import PromptEditor from "./config/PromptEditor.vue";
import ToolSection from "./config/ToolSection.vue";
import {
	makeDirective,
	normalizeDirectives,
	deriveMCPServers,
	resolutionIndex,
	toolDiscoveryState,
} from "./config/toolDirectives";

const props = defineProps({
	config: { type: Object, required: true },
	/** Changes when the panel switches nodes — the config object is reused. */
	nodeId: { type: String, default: "" },
	models: { type: Array, default: () => [] },
	allTools: { type: Array, default: () => [] },
	isLoadingTools: { type: Boolean, default: false },
	/** Raw list_user_tools response — carries the failures the tool list hides. */
	toolsResult: { type: Object, default: null },
	modelsError: { type: String, default: "" },
	/** Workflow-level global_settings.variables, for the prompt preview. */
	variables: { type: Object, default: () => ({}) },
	/** The workflow's default_user_id — whose tools this node actually gets. */
	runtimeUserLabel: { type: String, default: "this agent's user" },
	readonly: { type: Boolean, default: false },
});

const emit = defineEmits(["update", "reload-tools"]);

const resolution = ref(new Map());
const isResolving = ref(false);

const configuredTools = computed(() => props.config.tool_directives || []);

const discoveryState = computed(() =>
	toolDiscoveryState({ result: props.toolsResult, isLoading: props.isLoadingTools })
);

// Tier-grouped picker. `tier_rank` orders the groups; `display_name` is the
// only human label the models payload carries.
const modelGroups = computed(() => {
	const groups = new Map();
	for (const m of props.models) {
		if (!m?.model_id) continue;
		const tier = m.tier || m.tier_name || "Other";
		if (!groups.has(tier)) groups.set(tier, { tier, rank: m.tier_rank ?? 999, models: [] });
		groups.get(tier).models.push(m);
	}
	return [...groups.values()].sort((a, b) => a.rank - b.rank);
});

onMounted(() => {
	healDirectives();
	resolveTools();
});

// The panel reuses one config object across nodes, so the node id is the
// only signal that the directives under us have been swapped.
watch(
	() => props.nodeId,
	() => {
		healDirectives();
		resolveTools();
	}
);

function emitUpdate() {
	emit("update", { config: { ...props.config } });
}

function updatePrompt(value) {
	props.config.system_prompt = value;
	emitUpdate();
}

function setUseMemory(value) {
	props.config.use_memory = value;
	emitUpdate();
}

/**
 * Directives saved by an older builder carry the server-prefixed tool name,
 * which the engine can never resolve. Rewrite them once on open so the next
 * autosave persists the healed graph.
 */
function healDirectives() {
	if (props.readonly) return;
	const { directives, changed } = normalizeDirectives(configuredTools.value);
	if (!changed) return;
	props.config.tool_directives = directives;
	emitUpdate();
}

function addTool(tool) {
	const directives = [...configuredTools.value, makeDirective(tool)];
	props.config.tool_directives = directives;
	applyServerScoping(directives);
	emitUpdate();
	resolveTools();
}

function removeTool(idx) {
	const directives = configuredTools.value.filter((_, i) => i !== idx);
	props.config.tool_directives = directives;
	applyServerScoping(directives);
	emitUpdate();
	resolveTools();
}

function togglePriority(idx) {
	const directives = [...configuredTools.value];
	const d = directives[idx];
	if (!d) return;
	directives[idx] = { ...d, priority: d.priority === "primary" ? "secondary" : "primary" };
	props.config.tool_directives = directives;
	emitUpdate();
}

function setRequired(idx, value) {
	const directives = [...configuredTools.value];
	const d = directives[idx];
	if (!d) return;
	directives[idx] = { ...d, required: !!value };
	props.config.tool_directives = directives;
	emitUpdate();
}

// Never write [] — the engine reads an empty mcp_servers as "no filtering",
// which silently widens the node to every server the runtime user owns.
function applyServerScoping(directives) {
	const servers = deriveMCPServers(directives, props.allTools, props.config.mcp_servers || []);
	if (servers !== null) props.config.mcp_servers = servers;
}

async function resolveTools() {
	const directives = configuredTools.value;
	// Resolution is an admin-only endpoint; a viewer would only collect 403s.
	if (props.readonly || !directives.length) {
		resolution.value = new Map();
		return;
	}
	isResolving.value = true;
	try {
		const result = await api.workflows.resolveWorkflowTools(directives);
		resolution.value = resolutionIndex(result?.resolved || []);
	} catch (err) {
		logger.error("Failed to resolve workflow tools:", err);
		resolution.value = new Map();
	} finally {
		isResolving.value = false;
	}
}

function reloadTools() {
	emit("reload-tools");
	resolveTools();
}
</script>

<style scoped>
.config-section {
	margin-bottom: 1rem;
}

.config-label {
	display: block;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin-bottom: 0.375rem;
}

.config-label .optional {
	font-weight: 400;
	text-transform: none;
	letter-spacing: 0;
	opacity: 0.7;
}

.config-check-label {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	cursor: pointer;
}

.config-check-label input {
	accent-color: var(--ql-accent);
}

.config-input {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	box-sizing: border-box;
	transition: border-color 0.15s ease;
}

.config-input:focus {
	border-color: var(--ql-accent);
}

.config-select {
	cursor: pointer;
	appearance: none;
	background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
	background-position: right 0.5rem center;
	background-repeat: no-repeat;
	background-size: 1em;
	padding-right: 2rem;
}

.config-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0;
	line-height: 1.4;
}

.config-hint.error {
	color: var(--ql-danger);
}
</style>
