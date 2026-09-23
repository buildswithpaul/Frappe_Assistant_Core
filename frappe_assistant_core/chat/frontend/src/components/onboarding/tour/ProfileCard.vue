<template>
	<div class="carousel-slide">
		<div class="slide-visual anim-target" :class="{ 'anim-in': isActive }" :style="{ '--delay': '0s' }">
			<div class="profile-icon">
				<svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
					/>
				</svg>
			</div>
		</div>
		<h2 class="slide-title anim-target" :class="{ 'anim-in': isActive }" :style="{ '--delay': '0.1s' }">
			{{ title }}
		</h2>
		<p
			class="slide-description anim-target"
			:class="{ 'anim-in': isActive }"
			:style="{ '--delay': '0.15s' }"
		>
			{{ description }}
		</p>

		<div
			class="profile-form anim-target"
			:class="{ 'anim-in': isActive }"
			:style="{ '--delay': '0.25s' }"
		>
			<div class="profile-field">
				<label class="profile-label">Job Title</label>
				<input
					:value="jobTitle"
					@input="emit('update:jobTitle', $event.target.value)"
					type="text"
					class="profile-input"
					placeholder="e.g., Finance Manager"
					:disabled="saving"
				/>
			</div>
			<div class="profile-field">
				<label class="profile-label">Department</label>
				<input
					:value="department"
					@input="emit('update:department', $event.target.value)"
					type="text"
					class="profile-input"
					placeholder="e.g., Accounting"
					:disabled="saving"
				/>
			</div>
			<div class="profile-field">
				<label class="profile-label">
					AI Instructions
					<span class="profile-label-hint">optional</span>
				</label>
				<textarea
					:value="instructions"
					@input="emit('update:instructions', $event.target.value)"
					class="profile-textarea"
					rows="3"
					maxlength="1000"
					placeholder="e.g., Always format amounts in INR. Prefer tables."
					:disabled="saving"
				/>
			</div>
		</div>
		<p v-if="error" class="profile-error anim-target anim-in" :style="{ '--delay': '0s' }">
			{{ error }}
		</p>
	</div>
</template>

<script setup>
defineProps({
	isActive: { type: Boolean, default: false },
	title: { type: String, required: true },
	description: { type: String, required: true },
	jobTitle: { type: String, default: "" },
	department: { type: String, default: "" },
	instructions: { type: String, default: "" },
	saving: { type: Boolean, default: false },
	error: { type: String, default: null },
});
const emit = defineEmits(["update:jobTitle", "update:department", "update:instructions"]);
</script>

<style scoped>
.carousel-slide {
	min-width: 100%;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	text-align: center;
	padding: 1rem 0.5rem;
	min-height: 360px;
}

.slide-visual {
	margin-bottom: 1.25rem;
	min-height: 80px;
	display: flex;
	align-items: center;
	justify-content: center;
}

.profile-icon {
	width: 72px;
	height: 72px;
	border-radius: 1rem;
	background: var(--ql-accent-soft);
	display: flex;
	align-items: center;
	justify-content: center;
	color: var(--ql-accent);
}

.slide-title {
	font-family: var(--ql-font-serif);
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.5rem;
}

.slide-description {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
	margin: 0 0 1rem;
	max-width: 360px;
}

.profile-form {
	width: 100%;
	max-width: 360px;
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	margin-bottom: 0.5rem;
	text-align: left;
}

.profile-field {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.profile-label {
	display: flex;
	justify-content: space-between;
	align-items: baseline;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text);
}

.profile-label-hint {
	font-size: 0.7rem;
	font-weight: 400;
	color: var(--ql-text-muted);
}

.profile-input,
.profile-textarea {
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	font-family: inherit;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.profile-input:focus,
.profile-textarea:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 2px var(--ql-accent-soft);
}

.profile-input::placeholder,
.profile-textarea::placeholder {
	color: var(--ql-text-muted);
	opacity: 0.6;
}

.profile-textarea {
	resize: vertical;
	line-height: 1.45;
	min-height: 64px;
}

.profile-input:disabled,
.profile-textarea:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.profile-error {
	font-size: 0.75rem;
	color: var(--ql-danger);
	margin: 0.5rem 0 0;
	text-align: center;
}

/* Staggered entrance animations */
.anim-target {
	opacity: 0;
	transform: translateY(16px);
}

.anim-target.anim-in {
	animation: fadeSlideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
	animation-delay: var(--delay, 0s);
}

@keyframes fadeSlideUp {
	from {
		opacity: 0;
		transform: translateY(16px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}
</style>
