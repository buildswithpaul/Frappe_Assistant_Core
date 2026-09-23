<template>
	<div class="capability-review" data-test="capability-review">
		<h3 class="capability-review__title">{{ headline }}</h3>

		<!-- The tool array is the prompt-cache prefix, so adding this server
		     enlarges every future turn's prefix. That price leads the step,
		     stated in tools rather than tokens: this is a user-facing surface,
		     and tools are the unit the person choosing actually reasons about.
		     The spans are butted together on purpose: this reads as one
		     sentence, and is asserted as one. -->
		<p class="capability-review__cost" data-test="context-cost">
			<span class="capability-review__cost-verb">Adds </span
			><span class="capability-review__cost-figure">{{ toolPhrase }}</span
			><span class="capability-review__cost-tail"> to every conversation.</span>
		</p>

		<label class="capability-review__field">
			<span class="capability-review__label">Name this connection</span>
			<input
				v-model="name"
				data-test="server-name"
				type="text"
				class="capability-review__input"
				autocomplete="off"
			/>
		</label>

		<section class="capability-review__section">
			<div class="capability-review__section-head">
				<h4 class="capability-review__section-title">Tools</h4>
				<p class="capability-review__counts">
					<span data-test="resource-count">{{ resources.length }} {{ resourceNoun }}</span>
					<span aria-hidden="true">·</span>
					<span data-test="prompt-count">{{ prompts.length }} {{ promptNoun }}</span>
				</p>
			</div>

			<ul v-if="tools.length" class="capability-review__list">
				<li
					v-for="tool in tools"
					:key="tool.name"
					class="capability-review__row"
					data-test="tool-row"
				>
					<button
						type="button"
						class="capability-review__toggle"
						data-test="tool-toggle"
						:aria-expanded="Boolean(expanded[tool.name])"
						@click="toggle(tool.name)"
					>
						<svg
							viewBox="0 0 12 12"
							class="capability-review__caret"
							:class="{ 'is-open': expanded[tool.name] }"
							aria-hidden="true"
						>
							<path d="M4.5 3 7.5 6 4.5 9" />
						</svg>
						<span class="capability-review__tool">{{ tool.name }}</span>
					</button>
					<p
						v-if="expanded[tool.name] && tool.description"
						class="capability-review__description"
						data-test="tool-description"
					>
						{{ tool.description }}
					</p>
				</li>
			</ul>
			<!-- "Exposes no tools" is a claim about the server. We may only make
			     it when the server actually answered: a refused probe knows
			     nothing about what is behind it, and saying otherwise sends the
			     user looking for a fault on the wrong side. -->
			<p v-else-if="unmeasured" class="capability-review__empty" data-test="probe-failed">
				We couldn't read this server's tools.
				<span v-if="probeError" data-test="probe-error">{{ probeError }}</span>
			</p>
			<p v-else class="capability-review__empty">This server exposes no tools.</p>
		</section>

		<p v-if="error" class="capability-review__error" role="alert" data-test="review-error">
			{{ error }}
		</p>

		<div class="capability-review__actions">
			<button
				type="button"
				class="capability-review__cancel"
				data-test="cancel"
				:disabled="saving"
				@click="$emit('cancel')"
			>
				Cancel
			</button>
			<button
				type="button"
				class="capability-review__add"
				data-test="add"
				:disabled="saving"
				@click="add"
			>
				<span v-if="saving" class="capability-review__spinner" aria-hidden="true"></span>
				{{ saving ? "Adding…" : "Add connection" }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

const RESERVED_NAME = "Main Frappe Site";

const props = defineProps({
	capabilities: { type: Object, default: () => ({}) },
	suggestedName: { type: String, default: "" },
	existingNames: { type: Array, default: () => [] },
	saving: { type: Boolean, default: false },
});

const emit = defineEmits(["add", "cancel"]);

const name = ref(props.suggestedName);
const error = ref("");
const expanded = reactive({});

const tools = computed(() => props.capabilities?.tools || []);
const resources = computed(() => props.capabilities?.resources || []);
const prompts = computed(() => props.capabilities?.prompts || []);

const headline = computed(() =>
	props.suggestedName ? `${props.suggestedName} is ready to add` : "This server is ready to add"
);

// `measured` is false when the probe never got an answer — a refusal, not an
// empty server. AR sends the server's own sentence alongside it; for Slack that
// sentence carries the URL that fixes it.
const unmeasured = computed(() => props.capabilities?.measured === false);
const probeError = computed(() => props.capabilities?.error || "");

const toolCount = computed(() => props.capabilities?.tool_count ?? tools.value.length);
const toolPhrase = computed(() => `${toolCount.value} ${toolCount.value === 1 ? "tool" : "tools"}`);

const resourceNoun = computed(() => (resources.value.length === 1 ? "resource" : "resources"));
const promptNoun = computed(() => (prompts.value.length === 1 ? "prompt" : "prompts"));

function toggle(toolName) {
	expanded[toolName] = !expanded[toolName];
}

function validate(serverName) {
	if (!serverName) {
		return "Give this connection a name.";
	}
	// Exact, case-sensitive: AR grants managed status only on this precise
	// string, so a near-miss is not a security concern and must not read as one.
	if (serverName === RESERVED_NAME) {
		return `"${RESERVED_NAME}" is reserved for your managed Frappe site connection. Choose a different name.`;
	}
	if (props.existingNames.includes(serverName)) {
		return `You already have a connection named "${serverName}".`;
	}
	return "";
}

function add() {
	const serverName = name.value.trim();
	const message = validate(serverName);
	if (message) {
		error.value = message;
		return;
	}
	error.value = "";
	emit("add", { server_name: serverName });
}
</script>

<style scoped>
.capability-review {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-4);
}

.capability-review__title {
	margin: 0;
	font-size: 1.0625rem;
	font-weight: 600;
	line-height: 1.3;
	letter-spacing: -0.01em;
	color: var(--ql-text);
	word-break: break-word;
}

.capability-review__cost {
	margin: 0;
	padding: 0.75rem 0.875rem;
	border-radius: var(--ql-radius-md);
	border-left: 3px solid var(--ql-accent);
	background: var(--ql-accent-soft);
	line-height: 1.4;
}

.capability-review__cost-verb,
.capability-review__cost-tail {
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.capability-review__cost-figure {
	font-size: 1.0625rem;
	font-weight: 600;
	letter-spacing: -0.01em;
	color: var(--ql-text);
}

.capability-review__field {
	display: flex;
	flex-direction: column;
	gap: 0.3125rem;
}

.capability-review__label {
	font-size: 0.625rem;
	font-weight: 600;
	letter-spacing: 0.07em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.capability-review__input {
	padding: 0.5rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-bg);
	color: var(--ql-text);
	font: inherit;
	font-size: 0.875rem;
	outline: none;
}

.capability-review__input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.capability-review__section {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.capability-review__section-head {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 0.5rem;
}

.capability-review__section-title {
	margin: 0;
	font-size: 0.625rem;
	font-weight: 600;
	letter-spacing: 0.07em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.capability-review__counts {
	display: flex;
	gap: 0.375rem;
	margin: 0;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.capability-review__list {
	display: flex;
	flex-direction: column;
	margin: 0;
	padding: 0;
	list-style: none;
	max-height: 14rem;
	overflow-y: auto;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
}

.capability-review__row + .capability-review__row {
	border-top: 1px solid var(--ql-border);
}

.capability-review__toggle {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
	padding: 0.4375rem 0.75rem;
	background: none;
	border: none;
	font: inherit;
	text-align: left;
	cursor: pointer;
}

.capability-review__toggle:hover {
	background: var(--ql-subtle);
}

.capability-review__caret {
	flex: none;
	width: 0.625rem;
	height: 0.625rem;
	fill: none;
	stroke: var(--ql-text-muted);
	stroke-width: 1.6;
	stroke-linecap: round;
	stroke-linejoin: round;
	transition: transform 150ms ease;
}

.capability-review__caret.is-open {
	transform: rotate(90deg);
}

.capability-review__tool {
	font-family: var(--ql-font-mono);
	font-size: 0.75rem;
	color: var(--ql-text);
	word-break: break-all;
}

.capability-review__description {
	margin: 0;
	padding: 0 0.75rem 0.5rem 1.875rem;
	font-size: 0.6875rem;
	line-height: 1.5;
	color: var(--ql-text-secondary);
}

.capability-review__empty {
	margin: 0;
	padding: 0.625rem 0.75rem;
	border: 1px dashed var(--ql-border);
	border-radius: var(--ql-radius-md);
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.capability-review__error {
	margin: 0;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-danger);
}

.capability-review__actions {
	display: flex;
	align-items: center;
	justify-content: flex-end;
	gap: 0.5rem;
	padding-top: 0.875rem;
	border-top: 1px solid var(--ql-border);
}

.capability-review__add {
	display: inline-flex;
	align-items: center;
	gap: 0.4375rem;
	padding: 0.5625rem 1.125rem;
	border: 1px solid var(--ql-accent);
	border-radius: var(--ql-radius-md);
	background: var(--ql-accent);
	color: var(--ql-bg);
	font: inherit;
	font-size: 0.875rem;
	font-weight: 600;
	cursor: pointer;
}

.capability-review__add:hover:not(:disabled) {
	background: var(--ql-accent-hover);
	border-color: var(--ql-accent-hover);
}

.capability-review__cancel {
	padding: 0.5625rem 0.75rem;
	border: none;
	border-radius: var(--ql-radius-md);
	background: none;
	color: var(--ql-text-secondary);
	font: inherit;
	font-size: 0.8125rem;
	cursor: pointer;
}

.capability-review__cancel:hover:not(:disabled) {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.capability-review__add:disabled,
.capability-review__cancel:disabled {
	opacity: 0.55;
	cursor: default;
}

.capability-review__spinner {
	width: 0.75rem;
	height: 0.75rem;
	border: 2px solid color-mix(in srgb, currentColor 35%, transparent);
	border-top-color: currentColor;
	border-radius: 50%;
	animation: capability-review-spin 0.8s linear infinite;
}

@keyframes capability-review-spin {
	to {
		transform: rotate(360deg);
	}
}

@media (prefers-reduced-motion: reduce) {
	.capability-review__spinner {
		animation-name: none;
	}
}
</style>
