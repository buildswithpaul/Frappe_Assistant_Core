<template>
	<div class="s-controls">
		<button v-if="!editing" type="button" class="s-link" data-test="model-change" @click="editing = true">
			{{ __("Change") }}
		</button>
		<select
			v-else
			class="s-input"
			data-test="model-select"
			:value="modelId"
			:disabled="saving"
			@change="onChange"
		>
			<option value="">{{ __("Workspace default") }}</option>
			<optgroup v-for="group in groups" :key="group.tier" :label="group.tier">
				<option v-for="m in group.models" :key="m.model_id" :value="m.model_id">
					{{ m.display_name || m.model_id }}
				</option>
			</optgroup>
		</select>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	modelId: { type: String, default: "" },
	models: { type: Array, default: () => [] },
	saving: { type: Boolean, default: false },
});
const emit = defineEmits(["save"]);

const editing = ref(false);

const groups = computed(() => {
	const byTier = new Map();
	for (const m of props.models) {
		if (!m?.model_id) continue;
		const tier = m.tier || m.tier_name || __("Other");
		if (!byTier.has(tier)) byTier.set(tier, { tier, rank: m.tier_rank ?? 999, models: [] });
		byTier.get(tier).models.push(m);
	}
	return [...byTier.values()].sort((a, b) => a.rank - b.rank);
});

function onChange(event) {
	emit("save", event.target.value);
	editing.value = false;
}
</script>

<style scoped src="./setupControls.css"></style>
