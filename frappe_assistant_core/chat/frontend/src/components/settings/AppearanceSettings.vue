<template>
	<div class="appearance-settings">
		<section class="profile-section">
			<h3 class="section-title">Display</h3>
			<p class="section-description">
				Personalize how messages and content appear. These apply to this browser
				only — they aren't carried to your other devices.
			</p>

			<div v-for="row in rows" :key="row.key" class="setting-item">
				<div class="setting-info">
					<label class="setting-label" :for="`pref-${row.key}`">{{ row.label }}</label>
					<p class="setting-description">{{ row.description }}</p>
				</div>
				<label class="toggle">
					<input
						:id="`pref-${row.key}`"
						type="checkbox"
						:checked="row.get()"
						@change="row.set($event.target.checked)"
					/>
					<span class="toggle-slider"></span>
				</label>
			</div>
		</section>

		<section class="profile-section">
			<h3 class="section-title">Theme</h3>
			<p class="setting-description">
				Theme follows your Frappe settings. Press <kbd>Shift+Ctrl+G</kbd> to change.
			</p>
		</section>
	</div>
</template>

<script setup>
import { usePreferences } from "@/composables/usePreferences";

const { preferences, savePreferences } = usePreferences();

function pref(key) {
	return {
		get: () => preferences[key],
		set: (value) => {
			preferences[key] = value;
			savePreferences();
		},
	};
}

const rows = [
	{
		key: "chatWidth",
		label: "Wide chat layout",
		description: "Use more of the screen width for the conversation",
		get: () => preferences.chatWidth !== "cozy",
		set: (value) => {
			preferences.chatWidth = value ? "wide" : "cozy";
			savePreferences();
		},
	},
	{
		key: "showTimestamps",
		label: "Show message timestamps",
		description: "Display time for each message",
		...pref("showTimestamps"),
	},
	{
		key: "showRoutingChip",
		label: "Explain how replies ran",
		description: "Show which model answered, and flag turns that ran differently",
		...pref("showRoutingChip"),
	},
	{
		key: "reduceMotion",
		label: "Reduce motion",
		description: "Minimize animations throughout the interface",
		...pref("reduceMotion"),
	},
	{
		key: "highContrast",
		label: "High contrast mode",
		description: "Increase contrast for better visibility",
		...pref("highContrast"),
	},
	{
		key: "largeText",
		label: "Large text",
		description: "Increase font size throughout the interface",
		...pref("largeText"),
	},
];
</script>

<style scoped>
.appearance-settings {
	width: 100%;
	max-width: 1100px;
}

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
	margin: 0 0 0.5rem 0;
	line-height: 1.4;
}

.setting-item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 0.75rem 0;
	gap: 1rem;
}

.setting-item + .setting-item {
	border-top: 1px solid var(--ql-border);
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
	cursor: pointer;
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
