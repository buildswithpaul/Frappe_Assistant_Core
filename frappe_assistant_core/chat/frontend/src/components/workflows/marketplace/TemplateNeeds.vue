<template>
	<div v-if="hasAnything" class="detail-section needs">
		<h3 class="section-label">{{ __("Needs") }}</h3>
		<dl class="needs-list">
			<template v-if="needs?.modules.length">
				<dt>{{ __("Modules") }}</dt>
				<dd>{{ needs.modules.join(", ") }}</dd>
			</template>
			<template v-if="needs?.reports.length">
				<dt>{{ __("Reports") }}</dt>
				<dd>{{ needs.reports.join(", ") }}</dd>
			</template>
			<template v-if="tools.length">
				<dt>{{ __("Tools") }}</dt>
				<dd class="mono">{{ tools.join(", ") }}</dd>
			</template>
			<template v-if="needs?.writeTools.length">
				<dt>{{ __("Writes") }}</dt>
				<dd class="needs-writes">
					<span class="mono">{{ needs.writeTools.join(", ") }}</span>
					— {{ __("needs approval (Always allow) to run unattended") }}
				</dd>
			</template>
			<template v-if="needs?.minErpnext">
				<dt>{{ __("Version") }}</dt>
				<dd>{{ __("ERPNext {0} or later", [needs.minErpnext]) }}</dd>
			</template>
		</dl>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import { parseRequires } from "./templateSchema";

const props = defineProps({
	requires: { type: [Object, String], default: null },
	fallbackTools: { type: Array, default: () => [] },
});

const needs = computed(() => parseRequires(props.requires));
const tools = computed(() => (needs.value?.tools.length ? needs.value.tools : props.fallbackTools));
const hasAnything = computed(
	() =>
		tools.value.length > 0 ||
		!!needs.value?.modules.length ||
		!!needs.value?.reports.length ||
		!!needs.value?.writeTools.length ||
		!!needs.value?.minErpnext
);
</script>

<style scoped>
.detail-section {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}
.needs-list {
	display: grid;
	grid-template-columns: max-content 1fr;
	gap: 0.25rem 0.75rem;
	font-size: 0.8125rem;
	margin: 0;
}
.needs-list dt {
	color: var(--ql-text-muted);
}
.needs-list dd {
	color: var(--ql-text);
	margin: 0;
}
.needs-writes {
	color: var(--ql-warning);
}
.mono {
	font-family: var(--ql-font-mono);
}
.section-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}
</style>
