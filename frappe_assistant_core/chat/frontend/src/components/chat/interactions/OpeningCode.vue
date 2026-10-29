<template>
	<section v-if="loading || failed || blocks.length" class="opening-code" data-test="opening-code">
		<h4 class="opening-title">{{ __("Code on this DocType goes live") }}</h4>
		<p class="opening-note">
			{{ __("It ran for nobody while only system managers could open this DocType. This write opens it to other people.") }}
		</p>
		<div v-if="loading" class="opening-note" data-test="opening-code-loading">{{ __("Loading the code that goes live…") }}</div>
		<div v-else-if="failed" class="opening-missing" data-test="opening-code-missing">
			{{ __("Couldn't load the code on this DocType. Check it in Desk before approving.") }}
		</div>
		<CodePreview
			v-for="item in blocks"
			:key="item.key"
			:label="item.label"
			:code="item.code"
			:language="item.language"
		/>
	</section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { __ } from "@/utils/i18n";
import { api } from "@/api/client";
import CodePreview from "./CodePreview.vue";
import { openingCodeBlocks, openingTarget } from "./openingCode";

const props = defineProps({
	block: { type: Object, required: true },
});
// True while the code is loading: the card must not be approved unseen.
const emit = defineEmits(["blocking"]);

const entries = ref([]);
const loading = ref(false);
const failed = ref(false);
const blocks = computed(() => openingCodeBlocks(entries.value));
watch(loading, (value) => emit("blocking", value), { immediate: true });

async function load() {
	const target = openingTarget(props.block.tool_name, props.block.input);
	if (!target) return;
	loading.value = true;
	try {
		entries.value = (await api.tools.codeGoingLive(target)) ?? [];
	} catch {
		failed.value = true;
	} finally {
		loading.value = false;
	}
}

load();
</script>

<style scoped>
.opening-code {
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 10px 12px;
	border-radius: var(--ql-radius-md, 8px);
	background: var(--ql-gold-soft);
}

.opening-title {
	margin: 0;
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-text);
}

.opening-note {
	margin: 0;
	color: var(--ql-text-secondary);
}

.opening-missing {
	margin: 0;
	color: var(--ql-danger);
}
</style>
