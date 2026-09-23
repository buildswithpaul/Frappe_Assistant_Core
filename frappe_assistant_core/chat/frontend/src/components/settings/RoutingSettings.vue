<template>
	<div class="routing-settings">
		<header class="routing-header">
			<h2 class="routing-title">Model routing</h2>
			<p class="routing-intro">
				Rules that tell auto mode which grade of model to use. Everyone in the
				workspace can read them; an admin sets them.
			</p>
		</header>

		<!-- Only `off` is worth a banner. It is the platform kill switch, and
		     while it is set no rule here changes anything however it reads —
		     so saying nothing would leave an admin switching rules live and
		     watching them do nothing. -->
		<p v-if="mode === 'off'" class="routing-mode">
			<strong>Routing rules are switched off for FAC Cloud.</strong>
			Rules below are kept, but none of them is changing which model answers.
		</p>

		<section class="routing-section">
			<h3 class="routing-subtitle">Workspace rules</h3>

			<p v-if="loading" class="routing-empty">Loading…</p>
			<p v-else-if="loadError" class="routing-empty">
				Couldn't load the rules for this workspace.
				<button type="button" class="routing-retry" @click="reload">Try again</button>
			</p>
			<p v-else-if="!team.length" class="routing-empty">
				No rules yet.
				<template v-if="canManage">Add one below.</template>
			</p>

			<ul v-else-if="team.length" class="rule-list">
				<li v-for="rule in team" :key="rule.preference_id" class="rule-item">
					<div class="rule-body">
						<p class="rule-sentence">
							{{ sentence(rule) }}
							<!-- Learning vs Live is the only thing here that changes
							     what a member experiences, so it reads as a word next
							     to the rule rather than a state to infer from a
							     button's label. -->
							<span
								class="rule-mode"
								:class="isLive(rule) ? 'rule-mode-live' : 'rule-mode-learning'"
							>
								{{ isLive(rule) ? "Live" : "Learning" }}
							</span>
						</p>
						<p class="rule-meta">
							{{ metaLine(rule) }}
							<span v-if="rule.status !== 'active'" class="rule-badge">
								{{ rule.status }}
							</span>
						</p>
						<p v-if="!isLive(rule)" class="rule-hint">
							Matched and recorded, but not changing which model answers
							yet.
							<template v-if="canManage">
								Take it live when you're happy with what it's matching.
							</template>
						</p>
					</div>
					<div v-if="canManage" class="rule-controls">
						<button
							class="rule-link rule-link-primary"
							@click="setMode(rule)"
							:disabled="busy === rule.preference_id"
						>
							{{ isLive(rule) ? "Back to learning" : "Go live" }}
						</button>
						<button
							class="rule-link"
							@click="toggle(rule)"
							:disabled="busy === rule.preference_id"
						>
							{{ rule.status === "active" ? "Suspend" : "Enable" }}
						</button>
						<button
							class="rule-link rule-link-danger"
							@click="remove(rule)"
							:disabled="busy === rule.preference_id"
						>
							Delete
						</button>
					</div>
				</li>
			</ul>
		</section>

		<!-- Shown to everyone, editable by nobody here. An admin who can see
		     routing happen but cannot find the rule behind it has no way to
		     explain their own workspace. -->
		<section v-if="platform.length" class="routing-section">
			<h3 class="routing-subtitle">Set by FAC Cloud</h3>
			<p class="routing-empty">
				Defaults that apply to every workspace on FAC Cloud. Your own rules
				above take priority over these, and none of them can raise a reply
				above what your plan allows.
			</p>
			<ul class="rule-list">
				<li
					v-for="rule in platform"
					:key="rule.preference_id"
					class="rule-item rule-item-platform"
				>
					<div class="rule-body">
						<p class="rule-sentence">{{ sentence(rule) }}</p>
						<p class="rule-meta">Set by FAC Cloud</p>
					</div>
				</li>
			</ul>
		</section>

		<section v-if="canManage" class="routing-section">
			<h3 class="routing-subtitle">Add a rule</h3>
			<RoutingRuleForm @created="reload" @error="onError" />
		</section>

		<!-- The answer to "why does an old reply say a rule chose its model
		     when I deleted that rule?" — asked at the one place it gets
		     asked. Collapsed, because it is a record, not a workspace. -->
		<details v-if="removed.length" class="routing-removed">
			<summary class="routing-subtitle">
				Removed rules ({{ removed.length }})
			</summary>
			<p class="routing-empty routing-removed-note">
				These don't affect any new reply. They're kept so that older
				messages naming a rule still make sense.
			</p>
			<ul class="rule-list">
				<li
					v-for="rule in removed"
					:key="rule.preference_id"
					class="rule-item rule-item-removed"
				>
					<div class="rule-body">
						<p class="rule-sentence">{{ pastSentence(rule) }}</p>
						<p class="rule-meta">{{ removedMeta(rule) }}</p>
					</div>
				</li>
			</ul>
		</details>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import RoutingRuleForm from "./routing/RoutingRuleForm.vue";

const { showError, showSuccess } = useToast();

const team = ref([]);
const removed = ref([]);
const platform = ref([]);
const mode = ref("shadow");
const canManage = ref(false);
const loading = ref(true);
// A failed load is not an empty list: telling an admin "No rules yet" after a
// 500 says their workspace policy is gone.
const loadError = ref(false);
const busy = ref(null);

const KIND_PHRASE = {
	keyword: (v) => `a message mentions “${v}”`,
	doctype: (v) => `you're on a ${v}`,
	task_type: (v) => `the task is ${v}`,
};

function sentence(rule) {
	// A team rule's text is withheld from members who did not author it, so
	// the sentence has to read without it.
	const phrase = rule.match_value
		? KIND_PHRASE[rule.match_kind]?.(rule.match_value)
		: "a rule set by your workspace matches";
	return `When ${phrase || "this matches"}, use ${rule.target_tier}.`;
}

// Past tense throughout: a removed rule is a thing that happened, and the
// present tense is exactly what made an admin think it was still running.
function pastSentence(rule) {
	const phrase = rule.match_value
		? KIND_PHRASE[rule.match_kind]?.(rule.match_value)
		: "a rule set by your workspace matched";
	return `When ${phrase || "this matched"}, this used ${rule.target_tier}.`;
}

function removedOn(rule) {
	// Frappe sends "YYYY-MM-DD HH:MM:SS.ffffff", which is not ISO — Safari
	// returns Invalid Date for it. Read the day and build the date from parts.
	const day = (rule.modified || "").slice(0, 10);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return "";
	const [y, m, d] = day.split("-").map(Number);
	return new Date(y, m - 1, d).toLocaleDateString(undefined, {
		day: "numeric",
		month: "short",
		year: "numeric",
	});
}

function removedMeta(rule) {
	const when = removedOn(rule);
	const scope = rule.scope === "Tenant" ? "Workspace rule" : "Your rule";
	return when ? `${scope} · removed ${when}` : scope;
}

function metaLine(rule) {
	const matched = rule.match_count
		? `Matched ${rule.match_count} ${rule.match_count === 1 ? "time" : "times"}`
		: "Not matched yet";
	return `${matched} · set by ${rule.created_by_user_id}`;
}

async function reload() {
	loading.value = true;
	loadError.value = false;
	try {
		const data = await api.routingPreferences.list();
		team.value = data?.team || [];
		removed.value = data?.removed || [];
		platform.value = data?.platform || [];
		mode.value = data?.mode || "shadow";
		canManage.value = Boolean(data?.can_manage_team);
	} catch (err) {
		loadError.value = true;
		showError(err?.message || "Couldn't load routing rules.");
	} finally {
		loading.value = false;
	}
}

// A rule is live only when it says so itself. An absent or unrecognised value
// reads as learning, the same fail-safe the server applies — a rule that
// silently starts applying is the failure this whole feature guards against.
function isLive(rule) {
	return rule.rule_mode === "on";
}

async function setMode(rule) {
	busy.value = rule.preference_id;
	const next = isLive(rule) ? "shadow" : "on";
	try {
		await api.routingPreferences.setMode(rule.preference_id, next);
		showSuccess(
			next === "on"
				? "Rule is live. It'll shape replies from your next message."
				: "Rule is back to learning. It won't change replies.",
		);
		await reload();
	} catch (err) {
		showError(err?.message || "Couldn't change that rule.");
	} finally {
		busy.value = null;
	}
}

async function toggle(rule) {
	busy.value = rule.preference_id;
	const next = rule.status === "active" ? "suspended" : "active";
	try {
		await api.routingPreferences.setStatus(rule.preference_id, next);
		await reload();
	} catch (err) {
		showError(err?.message || "Couldn't change that rule.");
	} finally {
		busy.value = null;
	}
}

async function remove(rule) {
	busy.value = rule.preference_id;
	try {
		await api.routingPreferences.remove(rule.preference_id);
		showSuccess("Rule removed. It won't affect new replies.");
		await reload();
	} catch (err) {
		showError(err?.message || "Couldn't delete that rule.");
	} finally {
		busy.value = null;
	}
}

function onError(message) {
	showError(message);
}

onMounted(reload);
</script>

<style scoped>
.routing-settings {
	display: flex;
	flex-direction: column;
	gap: 1.5rem;
}

.routing-title {
	margin: 0 0 0.25rem;
	font-size: 1.125rem;
	color: var(--ql-text);
}

.routing-intro,
.routing-empty {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.routing-mode {
	margin: 0;
	padding: 0.625rem 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-subtle);
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.rule-mode {
	margin-left: 0.5rem;
	padding: 0.0625rem 0.375rem;
	border-radius: var(--ql-radius-sm);
	font-size: 0.6875rem;
	font-weight: 600;
	vertical-align: middle;
	white-space: nowrap;
}

.rule-mode-live {
	background: var(--ql-accent-soft, var(--ql-subtle));
	color: var(--ql-accent);
}

.rule-mode-learning {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}

.rule-hint {
	margin: 0.25rem 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.routing-section {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.routing-removed {
	border-top: 1px solid var(--ql-border);
	padding-top: 0.875rem;
}

.routing-removed summary {
	cursor: pointer;
}

.routing-removed-note {
	margin: 0.5rem 0 0.75rem;
}

.rule-item-removed {
	opacity: 0.65;
}

.rule-item-platform {
	border-left: 2px solid var(--ql-border);
	padding-left: 0.75rem;
}

.routing-subtitle {
	margin: 0;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.rule-list {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	margin: 0;
	padding: 0;
	list-style: none;
}

.rule-item {
	display: flex;
	gap: 1rem;
	align-items: flex-start;
	justify-content: space-between;
	padding: 0.75rem 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
}

.rule-sentence {
	margin: 0;
	font-size: 0.875rem;
	color: var(--ql-text);
}

.rule-meta {
	margin: 0.25rem 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.rule-badge {
	margin-left: 0.5rem;
	padding: 0.0625rem 0.375rem;
	border-radius: var(--ql-radius-sm);
	background: var(--ql-subtle);
	text-transform: capitalize;
}

.rule-controls {
	display: flex;
	gap: 0.75rem;
	flex-shrink: 0;
}

.rule-link {
	padding: 0;
	background: none;
	border: none;
	font: inherit;
	font-size: 0.75rem;
	color: var(--ql-accent);
	cursor: pointer;
}

.rule-link:disabled {
	opacity: 0.5;
	cursor: default;
}

.rule-link-primary {
	font-weight: 600;
}

.rule-link-danger {
	color: var(--ql-danger);
}

.routing-retry {
	margin-left: 0.375rem;
	padding: 0;
	background: none;
	border: none;
	font: inherit;
	color: var(--ql-accent);
	cursor: pointer;
	text-decoration: underline;
}
</style>
