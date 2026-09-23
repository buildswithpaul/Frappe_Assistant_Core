<template>
	<div class="run-node-section">
		<div class="run-header" @click="open = !open">
			<label class="config-label">Run Node</label>
			<svg
				class="run-chevron"
				:class="{ rotated: open }"
				width="14"
				height="14"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M19 9l-7 7-7-7"
				/>
			</svg>
		</div>

		<div v-if="open" class="run-body">
			<div v-if="isDirty" class="run-save-warning">
				<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
					/>
				</svg>
				<span>Unsaved changes will be saved first.</span>
			</div>

			<div class="run-input-wrap">
				<textarea
					v-model="inputText"
					class="config-input config-textarea mono"
					:placeholder="
						nodeType === 'agent'
							? 'Enter a message for the task...'
							: 'Enter text to transform...'
					"
					rows="3"
					:disabled="running"
				></textarea>
				<p class="config-hint">
					{{
						nodeType === "agent"
							? "Sent as the user message to the task."
							: "Text passed through the Jinja2 template."
					}}
				</p>
			</div>

			<button @click="handleRun" class="run-node-btn" :disabled="running">
				<template v-if="running">
					<div class="run-spinner"></div>
					Running... {{ elapsedText }}
				</template>
				<template v-else>
					<svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
						<path d="M8 5v14l11-7z" />
					</svg>
					Run
				</template>
			</button>

			<div v-if="result" class="run-result" :class="resultBorderClass">
				<div class="run-result-header">
					<span class="run-status-badge" :class="statusBadgeClass">{{
						result.status
					}}</span>
					<span class="run-result-meta">
						<span v-if="result.duration_ms">{{
							formatDuration(result.duration_ms)
						}}</span>
						<span v-if="result.credits_used"
							>{{ formatCredits(result.credits_used) }} credits</span
						>
					</span>
				</div>
				<div
					v-if="outputText"
					class="run-output markdown-body"
					v-html="renderedOutput"
				></div>
				<div v-if="errorText" class="run-error">{{ errorText }}</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps({
	nodeId: { type: String, required: true },
	nodeType: { type: String, required: true },
	isDirty: { type: Boolean, default: false },
	runNode: { type: Function, required: true },
	requestSave: { type: Function, required: true },
	waitForSave: { type: Function, required: true },
});

const open = ref(false);
const inputText = ref("");
const running = ref(false);
const result = ref(null);
const elapsedMs = ref(0);
let elapsedTimer = null;

const elapsedText = computed(() => {
	if (elapsedMs.value < 1000) return "";
	return `(${Math.floor(elapsedMs.value / 1000)}s)`;
});

const resultBorderClass = computed(() => {
	const s = result.value?.status;
	if (s === "Completed") return "result-completed";
	if (s === "Failed") return "result-failed";
	return "";
});

const statusBadgeClass = computed(() => {
	const s = result.value?.status;
	if (s === "Completed") return "status-completed";
	if (s === "Failed") return "status-failed";
	return "";
});

const outputText = computed(() => result.value?.node_result?.output_text || null);

const renderedOutput = computed(() => {
	if (!outputText.value) return "";
	return DOMPurify.sanitize(marked.parse(outputText.value));
});

const errorText = computed(() => {
	return (
		result.value?.node_result?.error_message ||
		(result.value?.status === "Failed" ? result.value?.error_message : null) ||
		null
	);
});

function formatDuration(ms) {
	if (ms < 1000) return `${ms}ms`;
	return `${(ms / 1000).toFixed(1)}s`;
}

// Per-node credits are small fractional values (e.g. 0.0034 from a
// classifier call). Match RunCard's local formatter so the same field
// reads consistently across both surfaces.
function formatCredits(credits) {
	if (!credits) return "";
	if (credits < 0.01) return credits.toFixed(4);
	if (credits < 1) return credits.toFixed(2);
	return credits.toFixed(1);
}

async function handleRun() {
	if (running.value) return;

	if (props.isDirty) {
		props.requestSave();
		await props.waitForSave();
	}

	running.value = true;
	result.value = null;
	elapsedMs.value = 0;

	const startTime = Date.now();
	elapsedTimer = setInterval(() => {
		elapsedMs.value = Date.now() - startTime;
	}, 200);

	try {
		result.value = await props.runNode(props.nodeId, inputText.value || "Test input");
	} catch (err) {
		result.value = { status: "Failed", error_message: err.message };
	} finally {
		running.value = false;
		clearInterval(elapsedTimer);
		elapsedTimer = null;
	}
}

// Reset when node changes
watch(
	() => props.nodeId,
	() => {
		result.value = null;
		running.value = false;
		elapsedMs.value = 0;
		if (elapsedTimer) {
			clearInterval(elapsedTimer);
			elapsedTimer = null;
		}
	}
);

onUnmounted(() => {
	if (elapsedTimer) {
		clearInterval(elapsedTimer);
		elapsedTimer = null;
	}
});
</script>

<style scoped>
.run-node-section {
	border-top: 1px solid var(--ql-border);
	padding-top: 1rem;
	margin-top: 0.5rem;
}

.run-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	cursor: pointer;
	user-select: none;
}

.run-header .config-label {
	margin-bottom: 0;
	cursor: pointer;
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

.run-chevron {
	color: var(--ql-text-muted);
	transition: transform 0.2s ease;
	flex-shrink: 0;
}

.run-chevron.rotated {
	transform: rotate(180deg);
}

.run-body {
	margin-top: 0.5rem;
}

.run-save-warning {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.375rem 0.5rem;
	font-size: 0.6875rem;
	color: var(--ql-warning);
	background: rgba(245, 158, 11, 0.08);
	border-radius: 0.25rem;
	margin-bottom: 0.5rem;
	line-height: 1.4;
}

.run-save-warning svg {
	flex-shrink: 0;
}

.run-input-wrap {
	margin-bottom: 0.5rem;
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

.config-textarea {
	resize: vertical;
	min-height: 3rem;
	font-family: inherit;
	line-height: 1.5;
}

.config-textarea.mono {
	font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
	font-size: 0.75rem;
	line-height: 1.6;
}

.config-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0;
	line-height: 1.4;
}

.run-node-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.375rem;
	width: 100%;
	padding: 0.5rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: opacity 0.15s ease;
}

.run-node-btn:hover:not(:disabled) {
	opacity: 0.9;
}

.run-node-btn:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

.run-spinner {
	width: 14px;
	height: 14px;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.run-result {
	margin-top: 0.5rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	overflow: hidden;
}

.run-result.result-completed {
	border-color: rgba(34, 197, 94, 0.3);
}

.run-result.result-failed {
	border-color: rgba(239, 68, 68, 0.3);
}

.run-result-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.375rem 0.5rem;
	background: var(--ql-subtle);
	gap: 0.5rem;
}

.run-status-badge {
	font-size: 0.5625rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
	text-transform: uppercase;
	letter-spacing: 0.025em;
}

.status-completed {
	background: rgba(34, 197, 94, 0.15);
	color: #16a34a;
}

.status-failed {
	background: rgba(239, 68, 68, 0.15);
	color: #dc2626;
}

.run-result-meta {
	display: flex;
	gap: 0.5rem;
	font-size: 0.625rem;
	color: var(--ql-text-muted);
}

.run-output {
	padding: 0.5rem;
	font-size: 0.75rem;
	line-height: 1.5;
	color: var(--ql-text);
	background: var(--ql-bg);
	max-height: 200px;
	overflow-y: auto;
	word-break: break-word;
}

.run-output :deep(p) {
	margin: 0 0 0.5rem;
}
.run-output :deep(p:last-child) {
	margin-bottom: 0;
}
.run-output :deep(ul),
.run-output :deep(ol) {
	margin: 0 0 0.5rem;
	padding-left: 1.25rem;
}
.run-output :deep(code) {
	font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
	font-size: 0.6875rem;
	background: var(--ql-subtle);
	padding: 0.125rem 0.25rem;
	border-radius: 0.25rem;
}
.run-output :deep(pre) {
	margin: 0.375rem 0;
	padding: 0.375rem;
	background: var(--ql-subtle);
	border-radius: 0.25rem;
	overflow-x: auto;
}
.run-output :deep(pre code) {
	background: none;
	padding: 0;
}
.run-output :deep(h1),
.run-output :deep(h2),
.run-output :deep(h3),
.run-output :deep(h4),
.run-output :deep(h5),
.run-output :deep(h6) {
	font-size: 0.8125rem;
	font-weight: 600;
	margin: 0.375rem 0 0.25rem;
}
.run-output :deep(blockquote) {
	margin: 0.375rem 0;
	padding-left: 0.5rem;
	border-left: 2px solid var(--ql-border);
	color: var(--ql-text-muted);
}
.run-output :deep(table) {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.6875rem;
	margin: 0.375rem 0;
}
.run-output :deep(th),
.run-output :deep(td) {
	padding: 0.25rem 0.375rem;
	border: 1px solid var(--ql-border);
	text-align: left;
}
.run-output :deep(th) {
	background: var(--ql-subtle);
	font-weight: 600;
}
.run-output :deep(a) {
	color: var(--ql-accent);
}
.run-output :deep(hr) {
	border: none;
	border-top: 1px solid var(--ql-border);
	margin: 0.375rem 0;
}

.run-error {
	padding: 0.5rem;
	font-size: 0.75rem;
	line-height: 1.4;
	color: #dc2626;
	background: rgba(239, 68, 68, 0.06);
	word-break: break-word;
}
</style>
