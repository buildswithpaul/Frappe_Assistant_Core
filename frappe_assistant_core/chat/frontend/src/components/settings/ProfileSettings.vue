<template>
	<div class="profile-settings">
		<!-- Loading -->
		<div v-if="loading" class="loading-state">
			<div class="spinner"></div>
			<p>Loading profile...</p>
		</div>

		<!-- Error -->
		<div v-if="error" class="error-banner">
			<p>{{ error }}</p>
		</div>

		<!-- Success -->
		<transition name="fade">
			<div v-if="successMessage" class="success-banner">
				<p>{{ successMessage }}</p>
			</div>
		</transition>

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
						<label class="field-label">Display Name</label>
						<input
							v-model="displayName"
							type="text"
							class="field-input"
							placeholder="Your name"
						/>
					</div>

					<div class="field">
						<label class="field-label">Job Title</label>
						<input
							v-model="jobTitle"
							type="text"
							class="field-input"
							placeholder="e.g., Finance Manager, Sales Lead"
						/>
					</div>

					<div class="field">
						<label class="field-label">Department</label>
						<input
							v-model="department"
							type="text"
							class="field-input"
							placeholder="e.g., Accounting, Operations"
						/>
					</div>
				</div>

				<div class="field field-full">
					<label class="field-label">
						About
						<span class="char-count" :class="{ 'at-limit': aboutLength >= 480 }">
							{{ aboutLength }}/500
						</span>
					</label>
					<textarea
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
						placeholder="e.g., Always format amounts in INR. Prefer tables over bullet lists. Keep responses concise."
					/>
				</div>
			</section>

			<!-- Locale -->
			<section class="profile-section">
				<h3 class="section-title">Language & Region</h3>
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
						<label class="field-label">Timezone</label>
						<input
							v-model="timezone"
							type="text"
							class="field-input"
							placeholder="e.g., Asia/Kolkata, America/New_York"
						/>
					</div>
				</div>
			</section>

			<!-- Display -->
			<section class="profile-section">
				<h3 class="section-title">Display</h3>
				<p class="section-description">
					Personalize how messages and content appear.
				</p>

				<div class="setting-item">
					<div class="setting-info">
						<label class="setting-label">Wide chat layout</label>
						<p class="setting-description">
							Use more of the screen width for the conversation
						</p>
					</div>
					<label class="toggle">
						<input
							type="checkbox"
							:checked="isWideChat"
							@change="toggleChatWidth"
						/>
						<span class="toggle-slider"></span>
					</label>
				</div>

				<div class="setting-item">
					<div class="setting-info">
						<label class="setting-label">Show message timestamps</label>
						<p class="setting-description">Display time for each message</p>
					</div>
					<label class="toggle">
						<input
							type="checkbox"
							v-model="preferences.showTimestamps"
							@change="savePreferences"
						/>
						<span class="toggle-slider"></span>
					</label>
				</div>

				<div class="setting-item">
					<div class="setting-info">
						<label class="setting-label">Reduce motion</label>
						<p class="setting-description">Minimize animations throughout the interface</p>
					</div>
					<label class="toggle">
						<input
							type="checkbox"
							v-model="preferences.reduceMotion"
							@change="savePreferences"
						/>
						<span class="toggle-slider"></span>
					</label>
				</div>

				<div class="setting-item">
					<div class="setting-info">
						<label class="setting-label">High contrast mode</label>
						<p class="setting-description">Increase contrast for better visibility</p>
					</div>
					<label class="toggle">
						<input
							type="checkbox"
							v-model="preferences.highContrast"
							@change="savePreferences"
						/>
						<span class="toggle-slider"></span>
					</label>
				</div>

				<div class="setting-item">
					<div class="setting-info">
						<label class="setting-label">Large text</label>
						<p class="setting-description">Increase font size throughout the interface</p>
					</div>
					<label class="toggle">
						<input
							type="checkbox"
							v-model="preferences.largeText"
							@change="savePreferences"
						/>
						<span class="toggle-slider"></span>
					</label>
				</div>
			</section>

			<!-- Appearance -->
			<section class="profile-section">
				<h3 class="section-title">Appearance</h3>
				<p class="setting-description">
					Theme follows your Frappe settings. Press <kbd>Shift+Ctrl+G</kbd> to change.
				</p>
			</section>

			<!-- Save -->
			<div class="save-bar">
				<button class="save-btn" :disabled="!isDirty || saving" @click="saveProfile">
					{{ saving ? "Saving..." : "Save Profile" }}
				</button>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useProfileData } from "@/composables/useProfileData";
import { usePreferences } from "@/composables/usePreferences";
import LanguageSelect from "@/components/settings/LanguageSelect.vue";

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
} = useProfileData();

const { preferences, savePreferences } = usePreferences();

const isWideChat = computed(() => preferences.chatWidth !== "cozy");

function toggleChatWidth() {
	preferences.chatWidth = isWideChat.value ? "cozy" : "wide";
	savePreferences();
}

onMounted(() => {
	loadProfile();
});
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

.success-banner {
	padding: 0.625rem 0.875rem;
	margin-bottom: 1rem;
	background: rgba(16, 185, 129, 0.08);
	border: 1px solid rgba(16, 185, 129, 0.2);
	border-radius: 0.5rem;
	color: var(--ql-success);
	font-size: 0.85rem;
}

.error-banner p,
.success-banner p {
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

/* Save bar */
.save-bar {
	display: flex;
	justify-content: flex-end;
	padding-top: 1rem;
	border-top: 1px solid var(--ql-border);
}

.save-btn {
	padding: 0.5rem 1.25rem;
	font-size: 0.85rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: opacity 0.15s ease;
}

.save-btn:hover:not(:disabled) {
	opacity: 0.9;
}

.save-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}

@media (max-width: 480px) {
	.field-grid {
		grid-template-columns: 1fr;
	}
}

.setting-item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 0.75rem 0;
	gap: 1rem;
}

.setting-info {
	flex: 1;
	min-width: 0;
}

.setting-label {
	display: block;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.setting-description {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.125rem;
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
	top: 0;
	left: 0;
	right: 0;
	bottom: 0;
	background-color: var(--ql-border);
	border-radius: 24px;
	transition: background-color 0.2s ease;
}

.toggle-slider::before {
	position: absolute;
	content: "";
	height: 18px;
	width: 18px;
	left: 3px;
	bottom: 3px;
	background-color: var(--ql-surface);
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

.toggle input:focus-visible + .toggle-slider {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}

kbd {
	display: inline-block;
	padding: 0.125rem 0.375rem;
	font-family: ui-monospace, monospace;
	font-size: 0.75rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.25rem;
	box-shadow: 0 1px 0 var(--ql-border);
}
</style>
