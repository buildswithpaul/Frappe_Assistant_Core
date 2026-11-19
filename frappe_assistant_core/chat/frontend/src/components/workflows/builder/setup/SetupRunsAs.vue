<template>
	<div class="s-controls">
		<p class="s-hint">{{ __("Agent steps use this person's connections and permissions.") }}</p>
		<div v-if="!editing" class="s-row">
			<button
				v-if="canUseMine && userId !== currentUser"
				type="button"
				class="s-btn"
				:class="{ primary: !userId }"
				data-test="run-as-me"
				:disabled="saving"
				@click="$emit('save', currentUser)"
			>
				{{ __("Run as me") }}
			</button>
			<button type="button" class="s-link" data-test="run-as-other" @click="startEditing">
				{{ userId ? __("Change") : __("Someone else…") }}
			</button>
		</div>
		<form v-else class="s-row" @submit.prevent="submit">
			<input
				ref="inputEl"
				v-model.trim="draft"
				class="s-input s-grow"
				type="email"
				data-test="run-as-input"
				:placeholder="__('user@example.com')"
			/>
			<button type="submit" class="s-btn primary" :disabled="!draft || saving">{{ __("Save") }}</button>
			<button type="button" class="s-link" @click="editing = false">{{ __("Cancel") }}</button>
		</form>
	</div>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	userId: { type: String, default: "" },
	currentUser: { type: String, default: "" },
	saving: { type: Boolean, default: false },
});
const emit = defineEmits(["save"]);

// AR keys tenant users by email; a Frappe username like "Administrator" would
// never resolve, so it is not offered as a one-click choice.
const canUseMine = computed(() => props.currentUser.includes("@"));

const editing = ref(false);
const draft = ref("");
const inputEl = ref(null);

async function startEditing() {
	draft.value = props.userId;
	editing.value = true;
	await nextTick();
	inputEl.value?.focus();
}

function submit() {
	emit("save", draft.value);
	editing.value = false;
}
</script>

<style scoped src="./setupControls.css"></style>
