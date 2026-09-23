<script setup>
import { computed, ref, onMounted } from "vue";
import { useVoiceCapture } from "@/composables/useVoiceCapture";
import { api } from "@/api/client";
import { resolveWhisperLanguage } from "@/constants/whisperLanguages";

const emit = defineEmits(["transcribed", "error"]);

// User's chosen language for transcription. Loaded once from AR Tenant
// User.locale; falls back to browser locale, then "en". Updates here are
// not reactive to Profile changes mid-session by design — users save the
// profile and the next page reload picks it up.
const profileLocale = ref("");

onMounted(async () => {
	try {
		const data = await api.profile.get();
		if (data && data.locale) profileLocale.value = data.locale;
	} catch {
		// Profile fetch is best-effort. Fall through to browser locale.
	}
});

async function postAudio(blob, durationMs) {
	const formData = new FormData();
	formData.append("audio", blob, "audio.webm");
	formData.append("duration_ms", String(durationMs));
	formData.append("language", resolveWhisperLanguage(profileLocale.value));
	const res = await fetch("/api/method/frappe_assistant_core.chat.api.voice.transcribe", {
		method: "POST",
		headers: { "X-Frappe-CSRF-Token": window.csrf_token || (window.frappe && window.frappe.csrf_token) || "" },
		body: formData,
		credentials: "same-origin",
	});
	const json = await res.json();
	const data = json.message || json;
	if (!res.ok || !data || data.text === undefined) {
		emit("error", "transcribe-failed");
		return;
	}
	if (!data.text) {
		emit("error", "empty");
		return;
	}
	emit("transcribed", data.text);
}

const { state, elapsed, toggle } = useVoiceCapture({
	onComplete: postAudio,
	onError: (reason, code) => emit("error", code),
});

const elapsedLabel = computed(() => {
	const total = Math.floor(elapsed.value);
	const m = Math.floor(total / 60);
	const s = total % 60;
	return `${m}:${s.toString().padStart(2, "0")}`;
});

const classMap = computed(() => ({
	"is-recording": state.value === "recording",
	"is-transcribing": state.value === "transcribing",
}));

const title = computed(() => {
	if (state.value === "recording") return "Tap to stop";
	if (state.value === "transcribing") return "Transcribing…";
	return "Voice input (Ctrl+Shift+Space)";
});
</script>

<template>
	<button class="mic-btn" type="button" :class="classMap" :title="title" :aria-label="title" @click="toggle">
		<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
			<path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
			<line x1="12" y1="19" x2="12" y2="23"></line>
			<line x1="8" y1="23" x2="16" y2="23"></line>
		</svg>
		<span v-if="state === 'recording'" class="elapsed">{{ elapsedLabel }}</span>
	</button>
</template>

<style scoped>
.mic-btn {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	height: 32px;
	min-width: 32px;
	padding: 0 6px;
	background: transparent;
	border: none;
	border-radius: 6px;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: background 0.15s ease, color 0.15s ease;
}

.mic-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.mic-btn.is-recording {
	color: #fff;
	background: #ef4444;
	animation: pulse 1.2s ease-in-out infinite;
}

.mic-btn.is-recording:hover { background: #dc2626; }

.mic-btn.is-transcribing svg {
	opacity: 0.5;
	animation: spin 1s linear infinite;
}

.elapsed {
	font-size: 12px;
	font-variant-numeric: tabular-nums;
	font-weight: 600;
}

@keyframes pulse {
	0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
	50%      { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
}

@keyframes spin {
	from { transform: rotate(0deg); }
	to   { transform: rotate(360deg); }
}
</style>
