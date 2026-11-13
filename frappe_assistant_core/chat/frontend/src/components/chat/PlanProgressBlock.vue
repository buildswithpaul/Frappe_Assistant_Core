<template>
	<!-- A migration plan this turn ran: its status and each file's, refreshed while it runs (#34351).
	     Only text said where it stood before; each file's own import shows the rows. -->
	<div v-if="plan" class="plan-progress" :class="{ ended: plan.ended }" role="status">
		<div class="pp-head">
			<span class="pp-title">{{ __("Migration plan {0}", [plan.plan]) }}</span>
			<span class="pp-status">{{ __(plan.status || "") }}</span>
		</div>
		<ol class="pp-files">
			<li v-for="file in plan.files" :key="file.session" class="pp-file">
				<span class="pp-name">{{ file.file_name || file.doctype }}</span>
				<span class="pp-file-status">{{ file.status_text || __(file.status || "") }}</span>
				<span class="pp-figures">
					{{ __("{0} created", [file.created || 0]) }}
					<span v-if="file.failed" class="pp-failed">{{ __("{0} failed", [file.failed]) }}</span>
					<span v-if="file.left_out" class="pp-left-out">{{ __("{0} left out", [file.left_out]) }}</span>
				</span>
			</li>
		</ol>
		<div class="pp-foot">
			<a v-if="url" class="pp-link" :href="url" target="_blank" rel="noopener">{{ __("Open in Desk") }}</a>
			<button
				v-if="plan.running && !stopAsked"
				type="button"
				class="pp-stop"
				:disabled="stopping"
				@click="stop"
			>
				{{ stopping ? __("Stopping…") : __("Stop after this file") }}
			</button>
		</div>
		<div v-if="stopNote" class="pp-note" :class="{ 'pp-refused': stopRefused }">{{ stopNote }}</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { api } from "@/api/client";
import { REFRESH_MS } from "@/composables/useImportProgress";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import { localizeSiteLink } from "@/utils/siteLinks";
import { safeUrl } from "@/utils/toolResult";

const props = defineProps({ plan: { type: String, required: true } });
const plan = ref(null);
let timer = null;
let stopped = false;

// Stop works without a chat turn (PR #392, F7): typed in the chat, "stop now" waited behind
// FACO's turn until the plan had finished. The server stops it through stop_migration_plan.
const stopping = ref(false);
const stopAsked = ref(false);
const stopNote = ref("");
const stopRefused = ref(false);

async function stop() {
	stopping.value = true;
	try {
		const reply = await api.imports.stopPlan(props.plan);
		stopRefused.value = !reply?.success;
		stopNote.value = reply?.success ? reply.message || __("The plan is stopping.") : reply?.error || __("The plan couldn't be stopped.");
		stopAsked.value = Boolean(reply?.success);
		if (reply?.progress) plan.value = reply.progress;
	} catch (e) {
		logger.warn("stop plan:", e);
		stopRefused.value = true;
		stopNote.value = __("The plan couldn't be stopped.");
	} finally {
		stopping.value = false;
	}
}

async function refresh() {
	try {
		plan.value = await api.imports.planProgress(props.plan);
	} catch (e) {
		logger.warn("plan progress:", e);
		return;
	}
	if (!stopped && !plan.value?.ended) timer = setTimeout(refresh, REFRESH_MS);
}

onMounted(refresh);
onBeforeUnmount(() => {
	stopped = true;
	clearTimeout(timer);
});

const url = computed(() => {
	const safe = safeUrl(plan.value?.url);
	return safe ? localizeSiteLink(safe) : null;
});
</script>

<style scoped>
.plan-progress {
	margin: 6px 0;
	padding: 10px 14px;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	background: var(--ql-subtle);
	color: var(--ql-text);
	font-size: 13px;
}
.pp-head {
	display: flex;
	justify-content: space-between;
	gap: 10px;
	flex-wrap: wrap;
	font-weight: 600;
	font-size: 14px;
}
.pp-status { color: var(--ql-text-muted); font-weight: 500; }
.pp-files { margin: 8px 0 4px; padding-left: 18px; }
.pp-file {
	display: flex;
	flex-wrap: wrap;
	gap: 4px 12px;
	padding: 2px 0;
}
.pp-name { font-weight: 500; overflow-wrap: anywhere; min-width: 0; }
.pp-file-status { color: var(--ql-text-muted); }
.pp-figures { color: var(--ql-text-muted); }
.pp-failed { color: var(--ql-danger, #c0392b); margin-left: 6px; }
.pp-left-out { margin-left: 6px; }
.pp-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.pp-link { font-size: 12px; }
.pp-stop {
	margin-left: auto;
	padding: 3px 10px;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	background: var(--ql-surface, transparent);
	color: var(--ql-danger, #c0392b);
	font-size: 12px;
	font-weight: 600;
	cursor: pointer;
}
.pp-stop:disabled { opacity: 0.6; cursor: default; }
.pp-note { margin-top: 6px; font-size: 12px; color: var(--ql-text-muted); }
.pp-refused { color: var(--ql-danger, #c0392b); }
</style>
