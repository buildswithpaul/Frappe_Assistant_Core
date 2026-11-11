<template>
	<div v-if="session" class="import-progress" :class="{ ended: session.ended }" role="status">
		<div class="ip-head">
			<span class="ip-title">
				{{ session.ended ? __("Import of {0}", [what]) : __("Importing {0}", [what]) }}
			</span>
			<span class="ip-status">{{ statusText }}</span>
		</div>
		<div class="ip-bar" aria-hidden="true">
			<div class="ip-fill" :style="{ width: (numbers?.percent || 0) + '%' }"></div>
		</div>
		<div class="ip-figures">
			<span v-if="numbers.total">{{ __("{0} of {1} rows", [numbers.done, numbers.total]) }}</span>
			<span>{{ __("{0} created", [numbers.created]) }}</span>
			<span v-if="numbers.failed" class="ip-failed">{{ __("{0} failed", [numbers.failed]) }}</span>
			<a v-if="url" class="ip-link" :href="url" target="_blank" rel="noopener">{{ __("Open in Desk") }}</a>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { figures, useImportProgress } from "@/composables/useImportProgress";
import { safeUrl } from "@/utils/toolResult";
import { localizeSiteLink } from "@/utils/siteLinks";
import { __ } from "@/utils/i18n";

const props = defineProps({ session: { type: String, required: true } });
const { state } = useImportProgress(computed(() => [props.session]));

const session = computed(() => state.sessions[props.session] || null);
const numbers = computed(() => figures(session.value) || { total: 0, done: 0, created: 0, failed: 0, percent: 0 });
const what = computed(() => session.value?.file_name || session.value?.doctype || props.session);
const statusText = computed(() => (session.value?.status ? __(session.value.status) : ""));
const url = computed(() => {
	const safe = safeUrl(session.value?.url);
	return safe ? localizeSiteLink(safe) : null;
});
</script>

<style scoped>
.import-progress {
	margin: 6px 0;
	padding: 10px 14px;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	background: var(--ql-subtle);
	color: var(--ql-text);
}
.ip-head {
	display: flex;
	justify-content: space-between;
	gap: 10px;
	flex-wrap: wrap;
	font-weight: 600;
}
.ip-title { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.ip-status { color: var(--ql-text-muted); font-weight: 500; }
.ip-bar {
	height: 6px;
	margin: 8px 0;
	border-radius: 3px;
	background: var(--ql-border);
	overflow: hidden;
}
.ip-fill {
	height: 100%;
	background: var(--ql-accent);
	transition: width 0.4s ease;
}
.ip-figures {
	display: flex;
	flex-wrap: wrap;
	gap: 4px 14px;
	font-size: 13px;
	color: var(--ql-text-muted);
}
.ip-failed { color: var(--ql-danger, #c0392b); }
.ip-link { color: var(--ql-accent); margin-left: auto; }
</style>
