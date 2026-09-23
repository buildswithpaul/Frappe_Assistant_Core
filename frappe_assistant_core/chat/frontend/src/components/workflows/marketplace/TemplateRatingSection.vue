<template>
	<div class="detail-section">
		<h3 class="section-label">Rating</h3>
		<div class="rating-display">
			<div class="stars-row">
				<svg
					v-for="i in 5"
					:key="'display-star-' + i"
					class="star-icon"
					width="16"
					height="16"
					viewBox="0 0 24 24"
					:fill="i <= Math.round(template.average_rating || 0) ? '#f59e0b' : 'none'"
					:stroke="
						i <= Math.round(template.average_rating || 0) ? '#f59e0b' : 'currentColor'
					"
				>
					<path
						d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
					/>
				</svg>
				<span class="rating-text">
					{{ (template.average_rating || 0).toFixed(1) }}
					<span class="rating-count"
						>({{ template.rating_count || 0 }} rating{{
							(template.rating_count || 0) !== 1 ? "s" : ""
						}})</span
					>
				</span>
			</div>

			<button v-if="!showForm" class="rate-btn" @click="showForm = true">
				Rate this template
			</button>

			<div v-if="showForm" class="rating-form">
				<div class="rate-stars">
					<svg
						v-for="i in 5"
						:key="'rate-star-' + i"
						class="star-icon clickable"
						width="20"
						height="20"
						viewBox="0 0 24 24"
						:fill="i <= (hoveredStar || userRating) ? '#f59e0b' : 'none'"
						:stroke="i <= (hoveredStar || userRating) ? '#f59e0b' : 'currentColor'"
						@mouseenter="hoveredStar = i"
						@mouseleave="hoveredStar = 0"
						@click="userRating = i"
					>
						<path
							d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
						/>
					</svg>
				</div>
				<textarea
					v-model="reviewText"
					class="review-textarea"
					placeholder="Write an optional review..."
					rows="2"
				></textarea>
				<div class="rating-actions">
					<button class="btn-secondary" @click="resetForm">Cancel</button>
					<button
						class="btn-primary"
						:disabled="!userRating || isSubmitting"
						@click="submitRating"
					>
						<span v-if="isSubmitting" class="loading-spinner small"></span>
						<span v-else>Submit</span>
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from "vue";

const props = defineProps({
	template: { type: Object, required: true },
	rating: { type: Number, default: 0 },
});

const emit = defineEmits(["rate"]);

const showForm = ref(false);
const userRating = ref(0);
const hoveredStar = ref(0);
const reviewText = ref("");
const isSubmitting = ref(false);

// Reset form state when template changes
watch(
	() => props.template,
	() => {
		resetForm();
	}
);

function resetForm() {
	showForm.value = false;
	userRating.value = 0;
	hoveredStar.value = 0;
	reviewText.value = "";
	isSubmitting.value = false;
}

function submitRating() {
	if (!userRating.value) return;
	isSubmitting.value = true;
	emit("rate", {
		rating: userRating.value,
		review: reviewText.value || null,
	});
}

/**
 * Called by the parent after the rating API call completes (success or failure)
 * to reset the form back to its idle state.
 */
function onRatingComplete() {
	resetForm();
}

defineExpose({ resetForm, onRatingComplete });
</script>

<style scoped>
.detail-section {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.section-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}

.rating-display {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.stars-row {
	display: flex;
	align-items: center;
	gap: 0.2rem;
}

.star-icon {
	color: var(--ql-text-muted);
	transition: all 0.1s ease;
}

.star-icon.clickable {
	cursor: pointer;
}

.star-icon.clickable:hover {
	transform: scale(1.15);
}

.rating-text {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-left: 0.375rem;
}

.rating-count {
	font-weight: 400;
	color: var(--ql-text-muted);
}

.rate-btn {
	align-self: flex-start;
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.rate-btn:hover {
	background: var(--ql-accent-soft);
}

.rating-form {
	display: flex;
	flex-direction: column;
	gap: 0.625rem;
	padding: 0.75rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.rate-stars {
	display: flex;
	gap: 0.25rem;
}

.review-textarea {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	resize: vertical;
	min-height: 3rem;
	font-family: inherit;
	box-sizing: border-box;
	transition: border-color 0.15s ease;
}

.review-textarea:focus {
	border-color: var(--ql-accent);
}

.rating-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
}

/* Buttons */
.btn-primary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
	opacity: 0.9;
}
.btn-primary:disabled {
	opacity: 0.5;
	cursor: default;
}

.btn-secondary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-secondary:hover {
	border-color: var(--ql-text);
}

/* Spinner */
.loading-spinner {
	width: 1rem;
	height: 1rem;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

.loading-spinner.small {
	width: 0.875rem;
	height: 0.875rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}
</style>
