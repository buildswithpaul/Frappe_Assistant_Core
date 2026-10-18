<template>
	<div class="home-settings">
		<section class="profile-section">
			<h3 class="section-title">{{ __("Home page") }}</h3>
			<p class="section-description">
				{{ __("Choose what appears on your home page. These choices are saved to your account.") }}
			</p>
			<p v-if="loadFailed" class="setting-description" role="alert">
				{{ __("Your home page settings could not be loaded. Refresh the page to try again.") }}
			</p>

			<template v-if="prefs">
				<div v-for="row in toggleRows" :key="row.key" class="setting-item">
					<div class="setting-info">
						<label class="setting-label" :for="`home-${row.key}`">{{ row.label }}</label>
						<p class="setting-description">{{ row.description }}</p>
					</div>
					<label class="toggle">
						<input
							:id="`home-${row.key}`"
							type="checkbox"
							:checked="prefs[row.key]"
							@change="save({ [row.key]: $event.target.checked })"
						/>
						<span class="toggle-slider"></span>
					</label>
				</div>

				<div class="setting-item">
					<div class="setting-info">
						<label class="setting-label" for="home-needs-you-count">{{ __("Cards to show") }}</label>
						<p class="setting-description">{{ __("The most Needs you cards shown at once.") }}</p>
					</div>
					<select
						id="home-needs-you-count"
						class="count-select"
						:value="prefs.needs_you_count"
						:disabled="!prefs.show_needs_you"
						@change="save({ needs_you_count: Number($event.target.value) })"
					>
						<option v-for="n in COUNT_OPTIONS" :key="n" :value="n">{{ n }}</option>
					</select>
				</div>
			</template>
		</section>

		<section v-if="prefs" class="profile-section">
			<fieldset class="signals" :disabled="!prefs.show_needs_you">
				<legend class="section-title">{{ __("Shown in Needs you") }}</legend>
				<p class="section-description">
					{{ __("Untick anything you do not want on your home page.") }}
				</p>
				<div v-for="signal in prefs.signals" :key="signal.id" class="signal-row">
					<input
						:id="`signal-${signal.id}`"
						type="checkbox"
						:checked="!prefs.hidden_signals.includes(signal.id)"
						@change="toggleSignal(signal.id, $event.target.checked)"
					/>
					<label :for="`signal-${signal.id}`">{{ signal.label }}</label>
				</div>
			</fieldset>
		</section>

		<p class="save-note" role="status">{{ saveNote }}</p>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { __ } from "@/utils/i18n";

const COUNT_OPTIONS = [1, 2, 3];

const { showError } = useToast();
const prefs = ref(null);
const loadFailed = ref(false);
const saveNote = ref("");
// The latest save wins: a slower, older response must not overwrite what the user did since.
let saveSeq = 0;

const toggleRows = computed(() => [
	{
		key: "show_needs_you",
		label: __("Needs you"),
		description: __("Approvals, overdue items and other things waiting on you."),
	},
	{
		key: "show_suggested_prompts",
		label: __("Suggested questions"),
		description: __("Show starter questions on your home page."),
	},
	{
		key: "show_personalized_suggestions",
		label: __("Personalised suggestions"),
		description: __("Uses AI about once a day to suggest questions for you. Turn off to save usage."),
	},
]);

onMounted(async () => {
	try {
		prefs.value = await api.home.getPreferences();
	} catch {
		loadFailed.value = true;
	}
});

async function save(patch) {
	const previous = prefs.value;
	const seq = ++saveSeq;
	prefs.value = { ...previous, ...patch };
	saveNote.value = "";
	try {
		const saved = await api.home.updatePreferences(patch);
		if (seq === saveSeq) prefs.value = saved;
		saveNote.value = __("Saved");
	} catch (error) {
		if (seq === saveSeq) prefs.value = previous;
		showError(error?.message || __("Could not save your home page settings."));
	}
}

function toggleSignal(id, shown) {
	const others = prefs.value.hidden_signals.filter((hiddenId) => hiddenId !== id);
	save({ hidden_signals: shown ? others : [...others, id] });
}
</script>

<style scoped>
.home-settings { width: 100%; max-width: 1100px; }
.profile-section {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	padding: 24px;
	margin-bottom: 24px;
}
.section-title { font-size: 16px; font-weight: 600; color: var(--ql-text); margin: 0 0 4px; padding: 0; }
.section-description { color: var(--ql-text-secondary); font-size: 13px; margin: 0 0 0.5rem; line-height: 1.4; }
.setting-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; gap: 1rem; }
.setting-item + .setting-item { border-top: 1px solid var(--ql-border); }
.setting-info { flex: 1; min-width: 0; }
.setting-label { display: block; font-size: 0.875rem; font-weight: 500; color: var(--ql-text); cursor: pointer; }
.setting-description { font-size: 0.75rem; color: var(--ql-text-muted); margin-top: 0.125rem; }
.toggle { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink: 0; }
.toggle input { opacity: 0; width: 100%; height: 100%; margin: 0; position: absolute; inset: 0; cursor: pointer; z-index: 1; }
.toggle-slider {
	position: absolute; inset: 0; background-color: var(--ql-border);
	border-radius: 24px; transition: background-color 0.2s ease;
}
.toggle-slider::before {
	position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px;
	background-color: var(--ql-surface); border-radius: 50%; transition: transform 0.2s ease;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
.toggle input:checked + .toggle-slider { background-color: var(--ql-accent); }
.toggle input:checked + .toggle-slider::before { transform: translateX(20px); }
.toggle input:focus-visible + .toggle-slider { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
.count-select {
	min-height: 44px; min-width: 72px; padding: 0 0.75rem;
	background: var(--ql-surface); color: var(--ql-text);
	border: 1px solid var(--ql-border); border-radius: 8px; font-family: var(--ql-font-sans);
}
.count-select:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
.signals { margin: 0; padding: 0; border: none; min-width: 0; }
.signals:disabled { opacity: 0.55; }
.signal-row { display: flex; align-items: center; gap: 0.75rem; min-height: 44px; font-size: 0.875rem; color: var(--ql-text); }
.signal-row input { width: 18px; height: 18px; accent-color: var(--ql-accent); }
.signal-row label { flex: 1; cursor: pointer; }
.save-note { min-height: 1.25em; margin: 0; font-size: 0.75rem; color: var(--ql-text-muted); }
</style>
