<template>
	<div class="email-preview">
		<div class="email-envelope">
			<template v-for="row in rows" :key="row.label">
				<span class="envelope-key">{{ row.label }}</span>
				<span class="envelope-value">{{ row.value }}</span>
			</template>
		</div>
		<!-- eslint-disable-next-line vue/no-v-html -- sanitised by renderMessageBody -->
		<div class="email-body" v-html="rendered.html"></div>
		<div v-if="hiddenNote" class="email-hidden">{{ hiddenNote }}</div>
		<div v-if="senderLine" class="email-sender">{{ senderLine }}</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import { renderMessageBody } from "@/utils/messageTools";

defineOptions({ name: "EmailPreview" });

const props = defineProps({
	preview: { type: Object, default: null },
	to: { type: Array, default: () => [] },
	cc: { type: Array, default: () => [] },
	subject: { type: String, default: "" },
	body: { type: String, default: "" },
});

const rows = computed(() =>
	[
		{ label: __("To"), value: (props.to || []).join(", ") },
		{ label: __("Cc"), value: (props.cc || []).join(", ") },
		{ label: __("Subject"), value: props.subject },
	].filter((row) => row.value),
);

const rendered = computed(() => renderMessageBody(props.body));

const hiddenNote = computed(() => {
	const count = rendered.value.hiddenCount;
	if (!count) return "";
	return count === 1
		? __("1 image or other element is not shown here but will be sent.")
		: __("{0} images or other elements are not shown here but will be sent.", [count]);
});

const senderLine = computed(() => {
	if (!props.preview) return "";
	if (props.preview.will_email === false) return __("Recorded on the ticket; Helpdesk won't email it.");
	return props.preview.sender ? __("Sends from {0}", [props.preview.sender]) : "";
});
</script>

<style scoped>
.email-envelope {
	display: grid;
	grid-template-columns: 64px 1fr;
	gap: 4px 10px;
	padding: 10px 14px;
	font-size: 12.5px;
	border-bottom: 1px solid var(--ql-border);
}

.envelope-key {
	color: var(--ql-text-muted);
}

.envelope-value {
	color: var(--ql-text);
	overflow-wrap: anywhere;
}

.email-body {
	padding: 12px 14px;
	max-height: 240px;
	overflow-y: auto;
	font-size: 13px;
	line-height: 1.5;
	color: var(--ql-text);
	overflow-wrap: anywhere;
	border-bottom: 1px solid var(--ql-border);
}

.email-body :deep(p) {
	margin: 0 0 8px;
}

.email-body :deep(p:last-child) {
	margin-bottom: 0;
}

.email-hidden {
	padding: 8px 14px;
	font-size: 12px;
	color: var(--ql-warning);
	border-bottom: 1px solid var(--ql-border);
}

.email-sender {
	padding: 8px 14px;
	font-size: 12px;
	color: var(--ql-text-secondary);
}
</style>
