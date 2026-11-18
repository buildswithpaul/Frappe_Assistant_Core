<template>
	<div class="tools-settings">
		<section class="profile-section">
			<h3 class="section-title">{{ __("Tools") }}</h3>
			<p v-if="loadFailed" class="setting-description" role="alert">
				{{ __("Your tool settings could not be loaded. Refresh the page to try again.") }}
			</p>

			<div v-else-if="loadAsNeeded !== null" class="setting-item">
				<div class="setting-info">
					<label class="setting-label" for="load-tools-as-needed">
						{{ __("Load tools as needed (recommended)") }}
					</label>
					<p class="setting-description">
						{{
							__(
								"FACO loads only the tools a conversation needs, which keeps answers faster and cheaper. Turn off to give FACO every tool on every message."
							)
						}}
					</p>
				</div>
				<label class="toggle">
					<input
						id="load-tools-as-needed"
						type="checkbox"
						:checked="loadAsNeeded"
						@change="save($event.target.checked)"
					/>
					<span class="toggle-slider"></span>
				</label>
			</div>
		</section>

		<p class="save-note" role="status">{{ saveNote }}</p>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { __ } from "@/utils/i18n";

const { showError } = useToast();
// null until the saved choice has loaded, so the toggle never flashes the wrong state.
const loadAsNeeded = ref(null);
const loadFailed = ref(false);
const saveNote = ref("");
// The latest save wins: a slower, older response must not overwrite what the user did since.
let saveSeq = 0;

onMounted(async () => {
	try {
		loadAsNeeded.value = (await api.tools.getLoading()).load_tools_as_needed;
	} catch {
		loadFailed.value = true;
	}
});

async function save(value) {
	const previous = loadAsNeeded.value;
	const seq = ++saveSeq;
	loadAsNeeded.value = value;
	saveNote.value = "";
	try {
		const saved = await api.tools.setLoading(value);
		if (seq === saveSeq) loadAsNeeded.value = saved.load_tools_as_needed;
		saveNote.value = __("Saved");
	} catch (error) {
		if (seq === saveSeq) loadAsNeeded.value = previous;
		showError(error?.message || __("Could not save your tool settings."));
	}
}
</script>

<style scoped>
.tools-settings { width: 100%; }
.profile-section {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	padding: 24px;
	margin-bottom: 24px;
}
.section-title { font-size: 16px; font-weight: 600; color: var(--ql-text); margin: 0 0 4px; padding: 0; }
.setting-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; gap: 1rem; }
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
.save-note { min-height: 1.25em; margin: 0; font-size: 0.75rem; color: var(--ql-text-muted); }
</style>
