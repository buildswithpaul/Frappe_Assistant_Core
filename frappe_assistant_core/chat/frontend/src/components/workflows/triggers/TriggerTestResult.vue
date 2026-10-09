<template>
	<div class="test-result" :class="tone" role="status">
		<p v-if="testing">{{ __("Testing against the latest document…") }}</p>
		<template v-else-if="result">
			<p v-if="!result.payload">{{ result.message || __("No document to test against.") }}</p>
			<template v-else>
				<p>
					{{
						result.would_fire
							? __("{0} would fire this trigger.", [result.sample_doc])
							: __("{0} would not fire this trigger — a filter does not match.", [result.sample_doc])
					}}
				</p>
				<p v-if="failedText" class="failed-filter" data-test="failed-filter">
					{{ __("Failed filter: {0}", [failedText]) }}
				</p>
				<p class="scope-note">
					{{ __("The test checks filters only, not the event or the changed fields.") }}
				</p>
				<details class="payload" @toggle="open = $event.target.open">
					<summary>{{ __("Payload the agent would receive") }}</summary>
					<pre v-if="open">{{ pretty }}</pre>
				</details>
			</template>
		</template>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	result: { type: Object, default: null },
	testing: { type: Boolean, default: false },
});

const open = ref(false);

const failedText = computed(() => {
	const f = props.result?.failed_filter;
	return f ? `${f.fieldname} ${f.operator} ${f.value ?? ""}`.trim() : "";
});

const tone = computed(() => (props.result?.payload ? (props.result.would_fire ? "ok" : "warn") : ""));
const pretty = computed(() => JSON.stringify(props.result?.payload ?? null, null, 2));
</script>

<style scoped>
.test-result {
	margin-top: 0.5rem;
	padding: 0.5rem 0.625rem;
	font-size: 0.75rem;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border-radius: var(--ql-radius-sm);
}
.test-result.ok {
	background: color-mix(in srgb, var(--ql-success) 10%, transparent);
}
.test-result.warn {
	background: color-mix(in srgb, var(--ql-warning) 12%, transparent);
}
.scope-note {
	color: var(--ql-text-secondary);
}
.payload pre {
	max-height: 16rem;
	overflow: auto;
	margin-top: 0.375rem;
	font-family: var(--ql-font-mono);
	font-size: 0.6875rem;
	white-space: pre-wrap;
	word-break: break-word;
}
</style>
