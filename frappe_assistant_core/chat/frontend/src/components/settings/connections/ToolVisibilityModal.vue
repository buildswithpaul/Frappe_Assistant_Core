<template>
	<div class="tool-visibility" @click.self="$emit('close')">
		<div class="tool-visibility__panel">
			<header class="tool-visibility__header">
				<div class="tool-visibility__heading">
					<h3 class="tool-visibility__title">Tools</h3>
					<p v-if="serverName" class="tool-visibility__subtitle">{{ serverName }}</p>
				</div>
				<button
					type="button"
					class="tool-visibility__close"
					aria-label="Close"
					@click="$emit('close')"
				>
					&times;
				</button>
			</header>

			<p v-if="!rows.length" class="tool-visibility__empty">This server exposes no tools.</p>

			<template v-else>
				<div class="tool-visibility__summary" data-test="summary">
					<span class="tool-visibility__tally">
						<b>{{ tally.always }}</b> always allowed
					</span>
					<span class="tool-visibility__tally"><b>{{ tally.ask }}</b> ask first</span>
					<span class="tool-visibility__tally"><b>{{ tally.blocked }}</b> blocked</span>
				</div>

				<input
					v-if="rows.length > 8"
					v-model="query"
					type="search"
					class="tool-visibility__search"
					placeholder="Filter tools"
					data-test="search"
				/>

				<div class="tool-visibility__scroll">
					<section
						v-for="group in visibleGroups"
						:key="group.key"
						class="tool-visibility__group"
					>
						<div class="tool-visibility__group-head">
							<div>
								<h4 class="tool-visibility__group-title">{{ group.title }}</h4>
								<p class="tool-visibility__group-note">{{ group.note }}</p>
							</div>
							<button
								type="button"
								class="tool-visibility__bulk"
								:data-test="`bulk-${group.key}`"
								@click="setGroup(group, group.key === 'read' ? 'always' : 'ask')"
							>
								{{ group.key === "read" ? "Allow all" : "Ask for all" }}
							</button>
						</div>

						<ul class="tool-visibility__list">
							<ToolPermissionRow
								v-for="tool in group.tools"
								:key="tool.name"
								v-model="choice[tool.name]"
								:tool="tool"
							/>
						</ul>
					</section>

					<p v-if="!visibleGroups.length" class="tool-visibility__empty">
						No tool matches “{{ query }}”.
					</p>
				</div>

				<p v-if="!managed && hasReadOnlyClaim" class="tool-visibility__caveat">
					Tools this server calls read-only run without asking you. That label is
					the server’s own description and not something we can verify, so move
					any you would rather be asked about to Ask.
				</p>
			</template>

			<footer class="tool-visibility__actions">
				<button
					type="button"
					class="tool-visibility__save"
					data-test="save"
					:disabled="saving"
					@click="save"
				>
					{{ saving ? "Saving…" : "Save" }}
				</button>
				<button
					type="button"
					class="tool-visibility__cancel"
					:disabled="saving"
					@click="$emit('close')"
				>
					Cancel
				</button>
			</footer>
		</div>
	</div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import ToolPermissionRow from "./ToolPermissionRow.vue";

const props = defineProps({
	serverName: { type: String, default: "" },
	// Names only — what the older callers pass. `toolDetails` supersedes it
	// when present, because only that carries the read-only claim.
	tools: { type: Array, default: () => [] },
	toolDetails: { type: Array, default: () => [] },
	blocked: { type: Array, default: () => [] },
	// Stored approval preferences, keyed by the name the MODEL sees, which is
	// prefixed with the server's slug on everything but the managed connection.
	preferences: { type: Object, default: () => ({}) },
	slug: { type: String, default: "" },
	managed: { type: Boolean, default: false },
	saving: { type: Boolean, default: false },
});

const emit = defineEmits(["save", "close"]);

const query = ref("");

const rows = computed(() =>
	props.toolDetails.length
		? props.toolDetails.map((t) => ({
				name: t.name,
				description: t.description || "",
				read_only: Boolean(t.read_only),
		  }))
		: props.tools.map((name) => ({ name, description: "", read_only: false }))
);

const hasReadOnlyClaim = computed(() => rows.value.some((t) => t.read_only));

// The model-visible name. `prefix_for` in AR leaves the managed connection's
// tools bare and prefixes everything else with the slug, and tool preferences
// are stored under that name — so this is the key, not the bare name.
function modelName(name) {
	return props.managed || !props.slug ? name : `${props.slug}_${name}`;
}

// A stored preference always wins — it is the user's own last word. Absent one,
// a tool that only reads is allowed: stopping to ask before every lookup is
// friction without a decision behind it. Connecting a server is where the trust
// is granted; AR seeds these preferences at connect time, and this default is
// what the picker shows for connections made before it did.
function currentChoice(tool) {
	if (props.blocked.includes(tool.name)) return "blocked";
	const stored = props.preferences[modelName(tool.name)];
	if (stored === "always_allow") return "always";
	if (stored === "block") return "blocked";
	if (stored === "ask") return "ask";
	return tool.read_only ? "always" : "ask";
}

const choice = reactive(
	Object.fromEntries(rows.value.map((tool) => [tool.name, currentChoice(tool)]))
);

const tally = computed(() => {
	const counts = { always: 0, ask: 0, blocked: 0 };
	for (const tool of rows.value) counts[choice[tool.name]] += 1;
	return counts;
});

const filtered = computed(() => {
	const needle = query.value.trim().toLowerCase();
	if (!needle) return rows.value;
	return rows.value.filter(
		(t) =>
			t.name.toLowerCase().includes(needle) ||
			t.description.toLowerCase().includes(needle)
	);
});

const visibleGroups = computed(() =>
	[
		{
			key: "read",
			title: "Reads only",
			note: "Looks things up without changing them.",
			tools: filtered.value.filter((t) => t.read_only),
		},
		{
			key: "write",
			title: "Can make changes",
			note: "Creates, edits or deletes. Asking first is the safe default.",
			tools: filtered.value.filter((t) => !t.read_only),
		},
	].filter((group) => group.tools.length)
);

function setGroup(group, value) {
	for (const tool of group.tools) choice[tool.name] = value;
}

function save() {
	const blocked_tools = rows.value
		.filter((tool) => choice[tool.name] === "blocked")
		.map((tool) => tool.name);

	// Only what actually moved, and only among tools that stay exposed: each
	// preference is its own round trip to AR, an unchanged one buys nothing,
	// and a blocked tool's approval preference is moot because the model never
	// sees it to call it.
	const preferences = rows.value
		.filter((tool) => choice[tool.name] !== "blocked")
		.filter((tool) => choice[tool.name] !== currentChoice(tool))
		.map((tool) => ({
			tool_name: modelName(tool.name),
			preference: choice[tool.name] === "always" ? "always_allow" : "ask",
		}));

	emit("save", { server_name: props.serverName, blocked_tools, preferences });
}
</script>

<style scoped>
.tool-visibility {
	position: fixed;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: var(--ql-space-4);
	background: rgba(0, 0, 0, 0.5);
	z-index: 1200;
}

.tool-visibility__panel {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-3);
	width: 100%;
	max-width: 40rem;
	max-height: 86vh;
	padding: var(--ql-space-6);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg);
	overflow: hidden;
}

.tool-visibility__header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: var(--ql-space-3);
}

.tool-visibility__title {
	margin: 0;
	font-size: 1.0625rem;
	font-weight: 600;
	letter-spacing: -0.01em;
	color: var(--ql-text);
}

.tool-visibility__subtitle {
	margin: 2px 0 0;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.tool-visibility__close {
	padding: 0 var(--ql-space-1);
	border: none;
	background: none;
	font-size: 1.375rem;
	line-height: 1;
	color: var(--ql-text-muted);
	cursor: pointer;
}

.tool-visibility__close:hover {
	color: var(--ql-text);
}

.tool-visibility__summary {
	display: flex;
	flex-wrap: wrap;
	gap: var(--ql-space-4);
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.tool-visibility__tally b {
	font-weight: 600;
	color: var(--ql-text);
}

.tool-visibility__search {
	padding: var(--ql-space-2) var(--ql-space-3);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-bg);
	font: inherit;
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.tool-visibility__search:focus {
	outline: none;
	border-color: var(--ql-accent);
}

.tool-visibility__scroll {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-4);
	overflow-y: auto;
}

.tool-visibility__group-head {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: var(--ql-space-3);
	margin-bottom: var(--ql-space-2);
}

.tool-visibility__group-title {
	margin: 0;
	font-size: 0.6875rem;
	font-weight: 600;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: var(--ql-text-secondary);
}

.tool-visibility__group-note {
	margin: 2px 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.tool-visibility__bulk {
	flex-shrink: 0;
	padding: 0;
	border: none;
	background: none;
	font: inherit;
	font-size: 0.75rem;
	color: var(--ql-accent);
	cursor: pointer;
}

.tool-visibility__bulk:hover {
	text-decoration: underline;
}

.tool-visibility__list {
	margin: 0;
	padding: 0;
	list-style: none;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	overflow: hidden;
}

.tool-visibility__caveat {
	margin: 0;
	padding: var(--ql-space-3);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-subtle);
	font-size: 0.75rem;
	line-height: 1.5;
	color: var(--ql-text-secondary);
}

.tool-visibility__empty {
	margin: 0;
	padding: var(--ql-space-8) 0;
	text-align: center;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.tool-visibility__actions {
	display: flex;
	gap: var(--ql-space-2);
	padding-top: var(--ql-space-1);
}

.tool-visibility__save {
	padding: var(--ql-space-2) var(--ql-space-4);
	border: 1px solid var(--ql-accent);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-accent);
	font: inherit;
	font-size: 0.8125rem;
	color: var(--ql-surface);
	cursor: pointer;
}

.tool-visibility__save:hover:not(:disabled) {
	background: var(--ql-accent-hover);
	border-color: var(--ql-accent-hover);
}

.tool-visibility__save:disabled,
.tool-visibility__cancel:disabled {
	opacity: 0.5;
	cursor: default;
}

.tool-visibility__cancel {
	padding: var(--ql-space-2) var(--ql-space-4);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: none;
	font: inherit;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	cursor: pointer;
}
</style>
