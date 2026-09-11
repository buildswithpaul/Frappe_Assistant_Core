<template>
	<div class="profile-settings">
		<!-- Loading -->
		<div v-if="loading" class="loading-state">
			<div class="spinner"></div>
			<p>Loading profile...</p>
		</div>

		<!-- Load errors surface here; save errors ride the save bar, which is
		     already where the user is looking. -->
		<div v-if="error && !showSaveBar" class="error-banner">
			<p>{{ error }}</p>
		</div>

		<!-- Content -->
		<template v-if="!loading">
			<!-- About You -->
			<section class="profile-section">
				<h3 class="section-title">About You</h3>
				<p class="section-description">
					Help the AI understand who you are. These details are included in every
					conversation.
				</p>

				<div class="field-grid">
					<div class="field">
						<label class="field-label" for="profile-display-name">Display Name</label>
						<input
							id="profile-display-name"
							v-model="displayName"
							type="text"
							class="field-input"
							placeholder="Your name"
						/>
					</div>

					<div class="field">
						<label class="field-label" for="profile-job-title">Job Title</label>
						<input
							id="profile-job-title"
							v-model="jobTitle"
							type="text"
							class="field-input"
							placeholder="e.g., Finance Manager, Sales Lead"
						/>
					</div>

					<div class="field">
						<label class="field-label" for="profile-department">Department</label>
						<input
							id="profile-department"
							v-model="department"
							type="text"
							class="field-input"
							placeholder="e.g., Accounting, Operations"
						/>
					</div>
				</div>

				<div class="field field-full">
					<label class="field-label" for="profile-about">
						About
						<span class="char-count" :class="{ 'at-limit': aboutLength >= 480 }">
							{{ aboutLength }}/500
						</span>
					</label>
					<textarea
						id="profile-about"
						v-model="about"
						class="field-textarea"
						rows="3"
						maxlength="500"
						placeholder="A brief description of what you do — e.g., 'I manage AP/AR for 3 subsidiaries using ERPNext'"
					/>
				</div>
			</section>

			<!-- AI Instructions -->
			<section class="profile-section">
				<h3 class="section-title">AI Instructions</h3>
				<div class="instructions-hint">
					<svg
						class="hint-icon"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						width="16"
						height="16"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
					<p>
						These instructions are sent to the AI at the start of every conversation.
						Use them to set your preferred tone, formatting, domain focus, or any
						standing preferences.
					</p>
				</div>
				<div class="field field-full">
					<textarea
						v-model="customInstructions"
						class="field-textarea field-code"
						rows="5"
						aria-label="AI instructions"
						placeholder="e.g., Always format amounts in INR. Prefer tables over bullet lists. Keep responses concise."
					/>
				</div>
			</section>

			<!-- Locale -->
			<section class="profile-section">
				<h3 class="section-title">Language &amp; Region</h3>
				<p class="section-description">
					Your spoken language determines what voice transcription expects to hear.
					Leave it blank for auto-detect (less reliable on short clips).
				</p>
				<div class="field-grid">
					<div class="field">
						<label class="field-label">Language</label>
						<LanguageSelect v-model="locale" placeholder="Auto-detect (not recommended)" />
					</div>
					<div class="field">
						<label class="field-label" for="profile-timezone">Timezone</label>
						<input
							id="profile-timezone"
							v-model="timezone"
							type="text"
							class="field-input"
							placeholder="e.g., Asia/Kolkata, America/New_York"
						/>
					</div>
				</div>
			</section>

			<!-- Exists only while something is pending, so a permanently greyed-out
			     button never implies unsaved work. -->
			<transition name="slide-up">
				<ProfileSaveBar
					v-if="showSaveBar"
					:dirty="isDirty"
					:saving="saving"
					:error="error"
					:success-message="successMessage"
					@save="saveProfile"
					@discard="discardChanges"
				/>
			</transition>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { useProfileData } from "@/composables/useProfileData";
import LanguageSelect from "@/components/settings/LanguageSelect.vue";
import ProfileSaveBar from "@/components/settings/profile/ProfileSaveBar.vue";

const {
	loading,
	saving,
	error,
	successMessage,
	displayName,
	jobTitle,
	department,
	about,
	customInstructions,
	locale,
	timezone,
	isDirty,
	aboutLength,
	loadProfile,
	saveProfile,
	discardChanges,
} = useProfileData();

const showSaveBar = computed(() => isDirty.value || saving.value || !!successMessage.value);

function onKeydown(event) {
	if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "s") return;
	if (!isDirty.value || saving.value) return;
	event.preventDefault();
	saveProfile();
}

onBeforeRouteLeave(() => {
	if (!isDirty.value) return true;
	return window.confirm("You have unsaved profile changes. Leave without saving?");
});

onMounted(() => {
	window.addEventListener("keydown", onKeydown);
	loadProfile();
});

onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
.profile-settings {
	width: 100%;
	max-width: 1100px;
}

/* Loading */
.loading-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 3rem 0;
	color: var(--ql-text-muted);
}

.spinner {
	width: 24px;
	height: 24px;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.6s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* Banners */
.error-banner {
	padding: 0.625rem 0.875rem;
	margin-bottom: 1rem;
	background: rgba(239, 68, 68, 0.08);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.5rem;
	color: var(--ql-danger);
	font-size: 0.85rem;
}

.error-banner p {
	margin: 0;
}

/* Sections */
.profile-section {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	padding: 24px;
	margin-bottom: 24px;
}

.section-title {
	font-size: 16px;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 4px;
}

.section-description {
	color: var(--ql-text-secondary);
	font-size: 13px;
	margin: 0 0 1rem 0;
	line-height: 1.4;
}

/* Field */
.field {
	max-width: 640px;
}

/* Field grid */
.field-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 16px;
	max-width: 640px;
	margin-bottom: 1rem;
}

.field-grid .field:nth-child(3) {
	grid-column: 1 / -1;
}

.field-full {
	margin-bottom: 1rem;
}

.field-label {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	font-size: 0.8rem;
	font-weight: 500;
	color: var(--ql-text);
	margin-bottom: 0.375rem;
}

.char-count {
	font-size: 0.7rem;
	font-weight: 400;
	color: var(--ql-text-muted);
}

.char-count.at-limit {
	color: var(--ql-warning);
}

.field-input {
	display: block;
	width: 100%;
	padding: 8px 12px;
	font-size: 0.85rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	outline: none;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field-input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.field-input::placeholder,
.field-textarea::placeholder {
	color: var(--ql-text-muted);
	opacity: 0.6;
}

.field-textarea {
	display: block;
	width: 100%;
	padding: 8px 12px;
	font-size: 0.85rem;
	font-family: inherit;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	outline: none;
	resize: vertical;
	line-height: 1.5;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field-textarea:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.field-code {
	font-family: "SF Mono", SFMono-Regular, ui-monospace, monospace;
	font-size: 0.8rem;
}

/* Instructions hint */
.instructions-hint {
	display: flex;
	gap: 0.5rem;
	padding: 0.75rem;
	margin-bottom: 0.75rem;
	background: var(--ql-accent-soft);
	border: 1px solid var(--ql-accent-soft);
	border-radius: 0.5rem;
}

.hint-icon {
	flex-shrink: 0;
	color: var(--ql-accent);
	margin-top: 1px;
}

.instructions-hint p {
	margin: 0;
	font-size: 0.78rem;
	color: var(--ql-text-muted);
	line-height: 1.45;
}

/* Transitions */
.slide-up-enter-active,
.slide-up-leave-active {
	transition: transform 0.18s ease, opacity 0.18s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
	transform: translateY(8px);
	opacity: 0;
}

:global(.reduce-motion) .slide-up-enter-active,
:global(.reduce-motion) .slide-up-leave-active {
	transition: none;
}

@media (max-width: 480px) {
	.field-grid {
		grid-template-columns: 1fr;
	}
}
</style>
