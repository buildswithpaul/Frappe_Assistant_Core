<template>
	<div v-if="shown.length" class="rail-group import-card">
		<div class="rail-group-label">{{ __("Imports") }}</div>
		<div v-for="session in shown" :key="session.session" class="ic-session">
			<div class="ic-head">
				<span class="ic-file" :title="session.file_name">{{ session.file_name || session.session }}</span>
				<a v-if="link(session)" class="ic-link" :href="link(session)" target="_blank" rel="noopener">{{
					__("Desk")
				}}</a>
			</div>
			<ol class="ic-steps">
				<li
					v-for="(step, index) in state.steps"
					:key="step.key"
					:class="stepClass(session, index)"
				>
					{{ step.label }}
				</li>
			</ol>
			<div class="ic-figures">
				<template v-if="figures(session).total">
					{{ __("{0} of {1} rows", [figures(session).done, figures(session).total]) }} ·
				</template>
				{{ __("{0} created", [figures(session).created]) }}
				<template v-if="figures(session).failed"> · {{ __("{0} failed", [figures(session).failed]) }}</template>
				<!-- the server's words, already translated: "All rows left out" (PR #392, L1) -->
				<template v-if="session.status_text"> · {{ session.status_text }}</template>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { figures, useImportProgress } from "@/composables/useImportProgress";
import { conversationImportSessions } from "@/utils/importSessions";
import { safeUrl } from "@/utils/toolResult";
import { localizeSiteLink } from "@/utils/siteLinks";
import { __ } from "@/utils/i18n";

const props = defineProps({ messages: { type: Array, default: () => [] } });
const names = computed(() => conversationImportSessions(props.messages));
const { state } = useImportProgress(names);

const shown = computed(() => names.value.map((name) => state.sessions[name]).filter(Boolean));

function stepClass(session, index) {
	const current = state.steps.findIndex((step) => step.key === session.step);
	if (index < current || (index === current && session.ended && session.step === "imported")) return "done";
	if (index === current) return "current";
	return "";
}

function link(session) {
	const safe = safeUrl(session.url);
	return safe ? localizeSiteLink(safe) : null;
}
</script>

<style scoped>
.ic-session { padding: 8px 0; border-top: 1px solid var(--ql-border); }
.ic-session:first-of-type { border-top: none; }
.ic-head { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; font-weight: 600; }
.ic-file { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.ic-link { color: var(--ql-accent); font-weight: 500; flex: none; }
.ic-steps {
	display: flex;
	flex-wrap: wrap;
	gap: 4px;
	list-style: none;
	margin: 6px 0;
	padding: 0;
	font-size: 12px;
}
.ic-steps li {
	padding: 2px 8px;
	border-radius: 999px;
	border: 1px solid var(--ql-border);
	color: var(--ql-text-muted);
}
.ic-steps li.done { color: var(--ql-text); border-color: var(--ql-accent); }
.ic-steps li.current { color: #fff; background: var(--ql-accent); border-color: var(--ql-accent); font-weight: 600; }
.ic-figures { font-size: 12px; color: var(--ql-text-muted); }
</style>
