<template>
	<form class="feedback-form" @submit.prevent="onSubmit">
		<div class="field">
			<span>How are we doing? <em class="optional">Optional</em></span>
			<div class="stars" role="radiogroup" aria-label="Rating">
				<button v-for="n in 5" :key="n" type="button" class="star"
					:class="{ filled: n <= rating }"
					:aria-label="`${n} star${n > 1 ? 's' : ''}`"
					@click="rating = n">★</button>
			</div>
		</div>

		<label class="field">
			<span>Category</span>
			<select v-model="category">
				<option value="Product">Product</option>
				<option value="Service">Service</option>
				<option value="Feature Request">Feature Request</option>
				<option value="Other">Other</option>
			</select>
		</label>

		<label class="field">
			<span>Comments</span>
			<textarea v-model.trim="comment" rows="4"
				placeholder="Tell us what's working or what could be better" />
		</label>

		<div class="actions">
			<button type="button" class="btn-ghost" @click="$emit('cancel')">Cancel</button>
			<button type="submit" class="btn-primary" :disabled="submitting || !canSubmit">
				{{ submitting ? "Submitting…" : "Submit" }}
			</button>
		</div>
	</form>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
	submitting: { type: Boolean, default: false },
});
const emit = defineEmits(["submit", "cancel"]);

const rating = ref(0);
const category = ref("Product");
const comment = ref("");

const canSubmit = computed(() => rating.value > 0 || comment.value.length > 0);

function onSubmit() {
	if (!canSubmit.value) return;
	emit("submit", {
		rating: rating.value || null,
		category: category.value,
		comment: comment.value,
	});
}
</script>

<style scoped>
.feedback-form { display: flex; flex-direction: column; gap: 0.75rem; }
.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field span { font-size: 0.85rem; font-weight: 600; color: var(--ql-text-secondary); }
.field span .optional { font-weight: 400; font-style: normal; color: var(--ql-text-muted); }
.field select, .field textarea {
	padding: 0.5rem; border: 1px solid var(--ql-border); border-radius: var(--ql-radius-sm); font: inherit;
	background: var(--ql-surface); color: var(--ql-text);
}
.field textarea::placeholder { color: var(--ql-text-muted); }
.field select:focus, .field textarea:focus { outline: none; border-color: var(--ql-accent); }
.stars { display: flex; gap: 0.25rem; }
.star { background: none; border: none; font-size: 1.5rem; color: var(--ql-border-hover); cursor: pointer; line-height: 1; }
.star.filled { color: var(--ql-gold); }
.actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem; }
.btn-primary { padding: 0.5rem 1rem; border-radius: var(--ql-radius-sm); border: none; background: var(--ql-accent); color: #fff; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: default; }
.btn-ghost { padding: 0.5rem 1rem; border-radius: var(--ql-radius-sm); border: 1px solid var(--ql-border); background: none; color: var(--ql-text-secondary); cursor: pointer; }
</style>
