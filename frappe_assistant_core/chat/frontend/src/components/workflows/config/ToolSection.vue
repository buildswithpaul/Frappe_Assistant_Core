<template>
	<div class="config-section tools-section">
		<div class="tools-header">
			<label class="config-label">{{ __("Tools") }}</label>
			<div class="tools-header-actions">
				<button
					v-if="directives.length"
					class="link-btn"
					:disabled="isResolving"
					:title="__('Re-check tool availability')"
					@click="$emit('recheck')"
				>
					{{ isResolving ? __("Checking…") : __("Re-check") }}
				</button>
				<button
					v-if="!readonly"
					class="add-tool-btn"
					:title="__('Add tool')"
					@click="showToolPicker = true"
				>
					<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2.5"
							d="M12 4v16m8-8H4"
						/>
					</svg>
					{{ __("Add") }}
				</button>
			</div>
		</div>

		<p v-if="directives.length" class="tools-caption">
			{{
				__(
					"Preferred / Optional only changes how the prompt asks for a tool. Required is the one the engine enforces."
				)
			}}
		</p>

		<p v-if="missingCount" class="tools-banner bad">
			{{
				__("{0} of {1} tools unavailable to {2}. The agent will run without them.", [
					missingCount,
					directives.length,
					userLabel,
				])
			}}
		</p>

		<ul v-if="failures.length && discoveryState !== 'auth'" class="tools-banner bad server-failures">
			<li v-for="f in failures" :key="f.server">
				{{ __("Couldn't reach {0}: {1}. Its tools are missing from the list.", [f.server, f.message]) }}
			</li>
		</ul>

		<ToolPicker
			v-if="showToolPicker"
			:all-tools="allTools"
			:selected-tool-keys="selectedToolKeys"
			:is-loading="isLoadingTools"
			:empty-message="emptyState.title"
			:model-value="showToolPicker"
			@update:model-value="showToolPicker = $event"
			@select="onSelect"
		/>

		<div v-if="directives.length" class="tool-cards">
			<ToolDirectiveCard
				v-for="(directive, idx) in directives"
				:key="directiveKey(directive) + idx"
				:directive="directive"
				:resolution="resolution.get(directiveKey(directive)) || null"
				:server="serverFor(directive)"
				:readonly="readonly"
				@remove="$emit('remove', idx)"
				@toggle-priority="$emit('toggle-priority', idx)"
				@toggle-required="(value) => $emit('toggle-required', idx, value)"
			/>
		</div>

		<div v-else-if="!showToolPicker" class="tools-empty-state" :class="emptyState.tone">
			<p class="empty-title">{{ emptyState.title }}</p>
			<p class="empty-subtitle">{{ emptyState.subtitle }}</p>
			<button
				v-if="emptyState.action === 'reconnect'"
				class="empty-action"
				:disabled="isReconnecting"
				@click="reconnect"
			>
				{{ isReconnecting ? __("Reconnecting…") : __("Reconnect {0}", [reconnectTarget]) }}
			</button>
			<button
				v-else-if="emptyState.action === 'retry'"
				class="empty-action"
				@click="$emit('reload-tools')"
			>
				{{ __("Try again") }}
			</button>
			<RouterLink
				v-else-if="emptyState.action === 'connect'"
				to="/settings/connections"
				class="empty-action"
			>
				{{ __("Open Settings → Connections") }}
			</RouterLink>
			<p v-if="reconnectError" class="empty-error">{{ reconnectError }}</p>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useUserStore } from "@/stores/userStore";
import { logger } from "@/utils/logger";
import ToolPicker from "./ToolPicker.vue";
import ToolDirectiveCard from "./ToolDirectiveCard.vue";
import { __ } from "@/utils/i18n";
import {
	directiveKey,
	serverFailures,
	serverForDirective,
	serversNeedingReconnect,
} from "./toolDirectives";

const props = defineProps({
	directives: { type: Array, default: () => [] },
	allTools: { type: Array, default: () => [] },
	isLoadingTools: { type: Boolean, default: false },
	/** Map of directive tool_name -> resolve_workflow_tools entry. */
	resolution: { type: Map, default: () => new Map() },
	isResolving: { type: Boolean, default: false },
	/** "ok" | "loading" | "failed" | "auth" | "no-servers" | "empty" */
	discoveryState: { type: String, default: "ok" },
	toolsResult: { type: Object, default: null },
	runtimeUserLabel: { type: String, default: "" },
	readonly: { type: Boolean, default: false },
});

const emit = defineEmits([
	"add",
	"remove",
	"toggle-priority",
	"toggle-required",
	"recheck",
	"reload-tools",
]);

const userStore = useUserStore();

const showToolPicker = ref(false);
const isReconnecting = ref(false);
const reconnectError = ref(null);

const selectedToolKeys = computed(
	() => new Set(props.directives.filter((d) => d.tool_name).map(directiveKey))
);

const missingCount = computed(
	() =>
		props.directives.filter(
			(d) => props.resolution.get(directiveKey(d))?.status === "missing"
		)
			.length
);

const failures = computed(() => serverFailures(props.toolsResult));

const userLabel = computed(() => props.runtimeUserLabel || __("this agent's user"));

const reconnectTarget = computed(
	() => serversNeedingReconnect(props.toolsResult)[0] || "Main Frappe Site"
);

// Distinct empty states — an expired token is not "no tools found".
const emptyState = computed(() => {
	switch (props.discoveryState) {
		case "loading":
			return { tone: "", title: __("Loading tools…"), subtitle: "", action: null };
		case "auth":
			return {
				tone: "bad",
				title: __("Tool discovery needs a reconnect"),
				subtitle: __("{0} rejected the stored credentials, so its tools could not be listed.", [
					reconnectTarget.value,
				]),
				action: "reconnect",
			};
		case "failed":
			return {
				tone: "bad",
				title: __("Could not list tools"),
				subtitle: __("The MCP servers could not be reached. The list below may be incomplete."),
				action: "retry",
			};
		case "no-servers":
			return {
				tone: "",
				title: __("No MCP servers connected"),
				subtitle: __("Connect a server before giving this task tools."),
				action: "connect",
			};
		default:
			return {
				tone: "",
				title: __("No tools configured"),
				subtitle: __("Add tools to give this task capabilities."),
				action: null,
			};
	}
});

// ToolPicker offers whole tools; the directive keeps only the bare name.
function onSelect(tool) {
	emit("add", tool);
	showToolPicker.value = false;
}

function serverFor(directive) {
	return serverForDirective(directive, props.allTools);
}

async function reconnect() {
	isReconnecting.value = true;
	reconnectError.value = null;
	try {
		const result = await userStore.reconnectServer(reconnectTarget.value);
		if (result?.success) emit("reload-tools");
		else reconnectError.value = result?.error || __("Reconnect failed");
	} catch (err) {
		logger.error("Tool reconnect failed:", err);
		reconnectError.value = err.message || __("Reconnect failed");
	} finally {
		isReconnecting.value = false;
	}
}
</script>

<style scoped>
.tools-section {
	position: relative;
}

.tools-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 0.375rem;
}

.tools-header .config-label {
	margin-bottom: 0;
}

.tools-header-actions {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.link-btn {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	cursor: pointer;
	padding: 0;
}

.link-btn:hover:not(:disabled) {
	color: var(--ql-accent);
}

.link-btn:disabled {
	cursor: default;
	opacity: 0.6;
}

.add-tool-btn {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.25rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.add-tool-btn:hover {
	background: color-mix(in srgb, var(--ql-accent) 10%, transparent);
}

.tools-caption {
	margin: 0 0 0.5rem;
	font-size: 0.6875rem;
	line-height: 1.4;
	color: var(--ql-text-muted);
}

.tools-banner {
	margin: 0 0 0.5rem;
	padding: 0.375rem 0.5rem;
	font-size: 0.6875rem;
	line-height: 1.4;
	border-radius: 0.25rem;
	color: var(--ql-danger);
	background: color-mix(in srgb, var(--ql-danger) 8%, transparent);
	border: 1px solid color-mix(in srgb, var(--ql-danger) 25%, transparent);
}

.tool-cards {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.tools-empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.25rem;
	padding: 1.25rem 0.75rem;
	text-align: center;
}

.tools-empty-state .empty-title {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	margin: 0;
}

.tools-empty-state.bad .empty-title {
	color: var(--ql-danger);
}

.tools-empty-state .empty-subtitle {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0;
	line-height: 1.4;
}

.empty-action {
	margin-top: 0.5rem;
	padding: 0.25rem 0.625rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.25rem;
	cursor: pointer;
}

.empty-action:disabled {
	opacity: 0.6;
	cursor: default;
}

.empty-error {
	margin: 0.375rem 0 0;
	font-size: 0.6875rem;
	color: var(--ql-danger);
}

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
</style>
