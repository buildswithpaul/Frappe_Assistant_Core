<template>
	<!-- Internal tools: slim inline indicator -->
	<div v-if="block.isInternal" class="internal-tool">
		<div class="internal-tool-icon" :class="`icon-${block.status}`">
			<svg
				v-if="block.status === 'running'"
				class="status-spinner"
				viewBox="0 0 24 24"
				fill="none"
			>
				<circle
					cx="12"
					cy="12"
					r="10"
					stroke="currentColor"
					stroke-width="2"
					opacity="0.25"
				/>
				<path
					d="M12 2a10 10 0 0 1 10 10"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
				/>
			</svg>
			<svg
				v-else-if="block.status === 'success'"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M5 13l4 4L19 7"
				/>
			</svg>
			<svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
		</div>
		<span class="internal-tool-label">{{ internalLabel }}</span>
		<span v-if="duration" class="internal-tool-duration">{{ duration }}</span>
	</div>

	<!-- Normal tools: full expandable block -->
	<div
		v-else
		class="tool-block"
		:class="[`tool-status-${block.status}`, { 'tool-expanded': block.isExpanded }]"
	>
		<!-- Tool Header -->
		<button
			v-if="showHeader"
			class="tool-header"
			@click="$emit('toggle', block.id)"
			:aria-expanded="block.isExpanded"
		>
			<!-- Tool Icon -->
			<div class="tool-icon" :class="`icon-${block.status}`">
				<!-- Running spinner -->
				<svg
					v-if="block.status === 'running'"
					class="status-spinner"
					viewBox="0 0 24 24"
					fill="none"
				>
					<circle
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="2"
						opacity="0.25"
					/>
					<path
						d="M12 2a10 10 0 0 1 10 10"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
					/>
				</svg>
				<!-- Success checkmark -->
				<svg
					v-else-if="block.status === 'success'"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M5 13l4 4L19 7"
					/>
				</svg>
				<!-- Error X -->
				<svg
					v-else-if="block.status === 'error'"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
				<!-- Cancelled -->
				<svg
					v-else-if="block.status === 'cancelled'"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
					/>
				</svg>

				<!-- Default tool icon -->
				<svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
					/>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
					/>
				</svg>
			</div>

			<!-- Tool Name -->
			<span class="tool-name">{{ formatToolName(block.tool_name) }}</span>

			<!-- Status Badge -->
			<span class="tool-status-badge" :class="`badge-${block.status}`">
				{{ statusLabel }}
			</span>

			<!-- Duration -->
			<span v-if="duration" class="tool-duration">{{ duration }}</span>

			<!-- Chevron -->
			<svg
				class="tool-chevron"
				:class="{ 'chevron-expanded': block.isExpanded }"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 5l7 7-7 7"
				/>
			</svg>
		</button>

		<!-- Expanded Content (Input/Output) -->
		<div v-if="block.isExpanded" class="tool-content">
			<!-- Input Section -->
			<div v-if="hasInput" class="tool-section">
				<div class="section-label">Input:</div>
				<div class="section-code-wrapper">
					<pre
						class="section-code"
						:class="{ 'section-code-capped': !inputExpanded && inputOverflows }"
						ref="inputCodeRef"
						>{{ formatJson(block.input) }}</pre
					>
					<div v-if="inputOverflows && !inputExpanded" class="section-code-fade"></div>
					<button
						v-if="inputOverflows"
						class="section-toggle-btn"
						@click.stop="inputExpanded = !inputExpanded"
					>
						{{ inputExpanded ? "Show less" : "Show more" }}
					</button>
				</div>
			</div>

			<!-- Result Section -->
			<div v-if="block.result" class="tool-section">
				<div class="section-label">Result:</div>
				<div class="section-code-wrapper">
					<pre
						class="section-code"
						:class="{
							'result-error': block.status === 'error',
							'section-code-capped': !resultExpanded && resultOverflows,
						}"
						ref="resultCodeRef"
						>{{ formatJson(block.result) }}</pre
					>
					<div v-if="resultOverflows && !resultExpanded" class="section-code-fade"></div>
					<button
						v-if="resultOverflows"
						class="section-toggle-btn"
						@click.stop="resultExpanded = !resultExpanded"
					>
						{{ resultExpanded ? "Show less" : "Show more" }}
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from "vue";

const props = defineProps({
	block: {
		type: Object,
		required: true,
	},
	// Off when an outer row already names the action and its status — the
	// header would otherwise repeat that line with an inert chevron.
	showHeader: {
		type: Boolean,
		default: true,
	},
});

const emit = defineEmits(["toggle"]);

// Code block height cap (300px)
const CODE_MAX_HEIGHT = 300;
const inputCodeRef = ref(null);
const resultCodeRef = ref(null);
const inputExpanded = ref(false);
const resultExpanded = ref(false);
const inputOverflows = ref(false);
const resultOverflows = ref(false);

function checkOverflows() {
	if (inputCodeRef.value) {
		inputOverflows.value = inputCodeRef.value.scrollHeight > CODE_MAX_HEIGHT;
	}
	if (resultCodeRef.value) {
		resultOverflows.value = resultCodeRef.value.scrollHeight > CODE_MAX_HEIGHT;
	}
}

watch(
	() => [props.block.isExpanded, props.block.result],
	() => {
		nextTick(checkOverflows);
	}
);

// Status label mapping
const statusLabel = computed(() => {
	const labels = {
		running: "Running",
		success: "Success",
		error: "Error",
		cancelled: "Cancelled",
	};
	return labels[props.block.status] || props.block.status;
});

// Calculate duration
const duration = computed(() => {
	if (!props.block.startTime || !props.block.endTime) return null;

	const start = new Date(props.block.startTime);
	const end = new Date(props.block.endTime);
	const diffMs = end - start;

	if (diffMs < 1000) {
		return `${diffMs}ms`;
	} else if (diffMs < 60000) {
		return `${(diffMs / 1000).toFixed(1)}s`;
	} else {
		const mins = Math.floor(diffMs / 60000);
		const secs = Math.floor((diffMs % 60000) / 1000);
		return `${mins}m ${secs}s`;
	}
});

// Friendly label for internal tools
const internalLabel = computed(() => {
	const name = props.block.tool_name;
	const input = props.block.input || {};

	if (name === "get_skill") {
		const skillId = input.skill_id || input.tool_name || "";
		if (props.block.status === "running") return `Loading skill: ${skillId}`;
		return `Loaded skill: ${skillId}`;
	}
	if (name === "delegate") {
		if (props.block.status === "running") return "Delegating subtask…";
		return "Delegated subtask";
	}
	if (name?.startsWith("workspace_")) {
		const file = input.file_path || input.path || "";
		const shortFile = file.split("/").pop() || "";
		const op = name.replace("workspace_", "");
		if (props.block.status === "running") return `${formatToolName(op)}...`;
		return `${formatToolName(op)}${shortFile ? ": " + shortFile : ""}`;
	}
	return formatToolName(name);
});

// Check if there's input to display
const hasInput = computed(() => {
	return props.block.input && Object.keys(props.block.input).length > 0;
});

// Format helpers
function formatToolName(name) {
	if (!name) return "Tool";
	return name
		.replace(/_/g, " ")
		.replace(/([a-z])([A-Z])/g, "$1 $2")
		.split(" ")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
}

/**
 * Format JSON object for display.
 * Handles special cases like AR tool results which come as:
 * [{ "text": "{...json string...}" }]
 */
function formatJson(obj) {
	if (!obj) return "";
	try {
		// Handle AR tool result format: array with text property containing JSON string
		let data = obj;

		// If it's an array, try to extract content
		if (Array.isArray(data) && data.length > 0) {
			// Check if first element has a 'text' property with JSON string
			if (data[0]?.text && typeof data[0].text === "string") {
				try {
					data = JSON.parse(data[0].text);
				} catch {
					// If parsing fails, use the text content as-is
					data = data[0].text;
				}
			} else {
				// Just use the first element if no text property
				data = data[0];
			}
		}

		// Now format the cleaned data
		if (typeof data === "string") {
			// Try to parse if it looks like JSON
			try {
				const parsed = JSON.parse(data);
				return JSON.stringify(parsed, null, 2);
			} catch {
				return data;
			}
		}

		return JSON.stringify(data, null, 2);
	} catch {
		return String(obj);
	}
}
</script>

<style scoped>
/* ================================================
   Tool Block — Borderless, flowing design
   ================================================ */

.tool-block {
	margin: 0.125rem 0;
	border-radius: 0.375rem;
	overflow: hidden;
	transition: background-color 0.2s ease;
}

.tool-block.tool-status-running {
	background-color: color-mix(in srgb, var(--ql-warning) 6%, transparent);
}

.tool-block.tool-status-error {
	background-color: color-mix(in srgb, var(--ql-danger) 6%, transparent);
}

/* Header */
.tool-header {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	width: 100%;
	padding: 0.375rem 0.25rem;
	background: transparent;
	border: none;
	cursor: pointer;
	text-align: left;
	color: var(--ql-text-muted);
	transition: color 0.15s ease;
}

.tool-header:hover {
	color: var(--ql-text-secondary);
}

.tool-icon {
	flex-shrink: 0;
	width: 0.875rem;
	height: 0.875rem;
}

.tool-icon svg {
	width: 100%;
	height: 100%;
}

.tool-icon.icon-running {
	color: var(--ql-warning);
}

.tool-icon.icon-success {
	color: var(--ql-text-muted);
}

.tool-icon.icon-error {
	color: var(--ql-danger);
}

.tool-icon.icon-cancelled {
	color: var(--ql-text-muted);
}

.status-spinner {
	animation: spin 1s linear infinite;
}

@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

.tool-name {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-muted);
}

.tool-status-badge {
	font-size: 0.625rem;
	padding: 0.0625rem 0.3125rem;
	border-radius: 0.1875rem;
	font-weight: 500;
	text-transform: uppercase;
	letter-spacing: 0.025em;
}

.badge-running {
	background-color: var(--ql-gold-soft);
	color: var(--ql-warning);
}

.badge-success {
	display: none; /* Hide success badge — checkmark icon is enough */
}

.badge-error {
	background-color: color-mix(in srgb, var(--ql-danger) 12%, transparent);
	color: var(--ql-danger);
}

.badge-cancelled {
	background-color: var(--ql-subtle);
	color: var(--ql-text-muted);
}

.tool-duration {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin-left: auto;
	opacity: 0.7;
}

.tool-chevron {
	flex-shrink: 0;
	width: 0.75rem;
	height: 0.75rem;
	color: var(--ql-text-muted);
	transition: transform 0.2s ease;
	opacity: 0.6;
}

.tool-chevron.chevron-expanded {
	transform: rotate(90deg);
}

/* Expanded content — indented with left border */
.tool-content {
	padding: 0.375rem 0.5rem 0.5rem 1.5rem;
	border-left: 2px solid var(--ql-border);
	margin-left: 0.4375rem;
}

.tool-section {
	margin-bottom: 0.5rem;
}

.tool-section:last-child {
	margin-bottom: 0;
}

.section-label {
	font-size: 0.6875rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	margin-bottom: 0.25rem;
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.section-code {
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
	font-size: 0.7rem;
	line-height: 1.5;
	padding: 0.5rem;
	background-color: var(--ql-subtle);
	border-radius: 0.375rem;
	overflow-x: auto;
	white-space: pre-wrap;
	word-break: break-word;
	margin: 0;
	color: var(--ql-text);
}

.section-code.result-error {
	background-color: color-mix(in srgb, var(--ql-danger) 8%, transparent);
	color: var(--ql-danger);
}

.section-code-wrapper {
	position: relative;
}

.section-code-capped {
	max-height: 300px;
	overflow: hidden;
}

.section-code-fade {
	position: absolute;
	bottom: 0;
	left: 0;
	right: 0;
	height: 2.5rem;
	background: linear-gradient(transparent, var(--ql-surface));
	border-radius: 0 0 0.375rem 0.375rem;
	pointer-events: none;
}

.section-toggle-btn {
	display: block;
	width: 100%;
	padding: 0.25rem;
	margin-top: 0.125rem;
	font-size: 0.6875rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: transparent;
	border: none;
	cursor: pointer;
	text-align: center;
	transition: opacity 0.15s ease;
}

.section-toggle-btn:hover {
	opacity: 0.8;
}

/* ================================================
   Internal Tool - Slim Inline Indicator
   ================================================ */

.internal-tool {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.1875rem 0.25rem;
}

.internal-tool-icon {
	flex-shrink: 0;
	width: 0.875rem;
	height: 0.875rem;
}

.internal-tool-icon svg {
	width: 100%;
	height: 100%;
}

.internal-tool-icon.icon-running {
	color: var(--ql-text-muted);
}

.internal-tool-icon.icon-success {
	color: var(--ql-text-muted);
}

.internal-tool-label {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	font-style: italic;
}

.internal-tool-duration {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	opacity: 0.7;
}
</style>
