<template>
	<div class="carousel-slide">
		<div class="slide-visual anim-target" :class="{ 'anim-in': isActive }" :style="{ '--delay': '0s' }">
			<div class="privacy-icon">
				<svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
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
			class="consent-toggles anim-target"
			:class="{ 'anim-in': isActive }"
			:style="{ '--delay': '0.25s' }"
		>
			<div class="consent-row">
				<div class="consent-label">
					<strong>AI Memory</strong>
					<span>Learn from your conversations</span>
				</div>
				<label class="toggle">
					<input
						type="checkbox"
						:checked="memoryConsent"
						@change="emit('update:memoryConsent', $event.target.checked)"
					/>
					<span class="toggle-slider"></span>
				</label>
			</div>
		</div>
		<p
			class="consent-footer anim-target"
			:class="{ 'anim-in': isActive }"
			:style="{ '--delay': '0.35s' }"
		>
			You can change this anytime in Settings &rarr; Privacy.
		</p>
	</div>
</template>

<script setup>
defineProps({
	isActive: { type: Boolean, default: false },
	title: { type: String, required: true },
	description: { type: String, required: true },
	memoryConsent: { type: Boolean, default: true },
});
const emit = defineEmits(["update:memoryConsent"]);
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

.privacy-icon {
	width: 72px;
	height: 72px;
	border-radius: 1rem;
	background: rgba(100, 116, 139, 0.1);
	display: flex;
	align-items: center;
	justify-content: center;
	color: var(--ql-text-muted);
	transition: transform 0.3s ease;
}

.anim-in .privacy-icon {
	animation: scaleIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) 0.05s forwards;
	transform: scale(0.8);
}

@keyframes scaleIn {
	from {
		transform: scale(0.8);
	}
	to {
		transform: scale(1);
	}
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

.consent-toggles {
	width: 100%;
	max-width: 360px;
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	margin-bottom: 0.75rem;
}

.consent-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	background: var(--ql-bg);
	border-radius: 0.75rem;
	border: 1px solid var(--ql-border);
}

.consent-label {
	display: flex;
	flex-direction: column;
	text-align: left;
}

.consent-label strong {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
}

.consent-label span {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.125rem;
}

.consent-footer {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0;
}

.toggle {
	position: relative;
	display: inline-block;
	width: 44px;
	height: 24px;
	flex-shrink: 0;
}

.toggle input {
	opacity: 0;
	width: 0;
	height: 0;
}

.toggle-slider {
	position: absolute;
	cursor: pointer;
	inset: 0;
	background-color: var(--ql-border);
	border-radius: 24px;
	transition: all 0.2s ease;
}

.toggle-slider::before {
	position: absolute;
	content: "";
	height: 18px;
	width: 18px;
	left: 3px;
	bottom: 3px;
	background-color: white;
	border-radius: 50%;
	transition: all 0.2s ease;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.toggle input:checked + .toggle-slider {
	background-color: var(--ql-accent);
}

.toggle input:checked + .toggle-slider::before {
	transform: translateX(20px);
}

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
