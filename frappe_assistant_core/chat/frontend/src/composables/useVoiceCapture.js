// Vue 3 composable wrapping the same MediaRecorder state machine as
// widget_voice_capture.js. Exposes reactive state + a toggle().

import { ref, onUnmounted } from "vue";

const MAX_SECONDS = 60;
const MIN_SECONDS = 1.0;
const TICK_MS = 100;

const MIME_CANDIDATES = [
	"audio/webm;codecs=opus",
	"audio/webm",
	"audio/mp4",
	"audio/ogg;codecs=opus",
];

function pickMimeType() {
	if (!window.MediaRecorder) return "audio/webm";
	for (const c of MIME_CANDIDATES) {
		if (MediaRecorder.isTypeSupported(c)) return c;
	}
	return "audio/webm";
}

/**
 * @param {object} options
 * @param {(blob: Blob, durationMs: number) => Promise<void>} options.onComplete
 * @param {(reason: string, code: string) => void} [options.onError]
 */
export function useVoiceCapture({ onComplete, onError = () => {} }) {
	const state = ref("idle"); // 'idle' | 'requesting' | 'recording' | 'transcribing' | 'error'
	const elapsed = ref(0);

	let mediaRecorder = null;
	let stream = null;
	let chunks = [];
	let startedAt = 0;
	let tickInterval = null;
	let hardCapTimer = null;
	let visibilityHandler = null;

	function cleanupTimers() {
		if (tickInterval) { clearInterval(tickInterval); tickInterval = null; }
		if (hardCapTimer) { clearTimeout(hardCapTimer); hardCapTimer = null; }
		if (visibilityHandler) {
			document.removeEventListener("visibilitychange", visibilityHandler);
			visibilityHandler = null;
		}
	}

	function cleanupStream() {
		if (stream) {
			stream.getTracks().forEach((t) => t.stop());
			stream = null;
		}
	}

	function setError(reason, code) {
		state.value = "error";
		onError(reason, code);
		setTimeout(() => { state.value = "idle"; }, 0);
	}

	async function start() {
		state.value = "requesting";
		try {
			stream = await navigator.mediaDevices.getUserMedia({ audio: true });
		} catch (err) {
			const code = err.name === "NotAllowedError" ? "permission-denied" : "no-mic";
			setError(err.message || String(err), code);
			return;
		}

		const mime = pickMimeType();
		try {
			mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
		} catch (err) {
			cleanupStream();
			setError(err.message || String(err), "recorder-error");
			return;
		}

		chunks = [];
		mediaRecorder.ondataavailable = (e) => {
			if (e.data && e.data.size > 0) chunks.push(e.data);
		};
		mediaRecorder.onstop = () => handleStop(mime);
		mediaRecorder.onerror = (e) => {
			cleanupStream();
			setError(e.error?.message || "recorder error", "recorder-error");
		};

		startedAt = Date.now();
		mediaRecorder.start();
		state.value = "recording";

		tickInterval = setInterval(() => {
			elapsed.value = (Date.now() - startedAt) / 1000;
		}, TICK_MS);

		hardCapTimer = setTimeout(() => {
			if (state.value === "recording") stop();
		}, MAX_SECONDS * 1000);

		visibilityHandler = () => {
			if (document.hidden && state.value === "recording") cancel();
		};
		document.addEventListener("visibilitychange", visibilityHandler);
	}

	function stop() {
		if (!mediaRecorder || mediaRecorder.state === "inactive") return;
		mediaRecorder.stop();
	}

	function cancel() {
		chunks = [];
		if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
		cleanupTimers();
		cleanupStream();
		state.value = "idle";
		elapsed.value = 0;
	}

	async function handleStop(mime) {
		cleanupTimers();
		cleanupStream();

		const durationMs = Date.now() - startedAt;
		const durationSec = durationMs / 1000;
		if (durationSec < MIN_SECONDS) {
			setError("Recording too short", "too-short");
			return;
		}
		if (chunks.length === 0) {
			setError("No audio captured", "recorder-error");
			return;
		}

		const blob = new Blob(chunks, { type: mime });
		state.value = "transcribing";
		try {
			await onComplete(blob, durationMs);
		} finally {
			state.value = "idle";
			elapsed.value = 0;
		}
	}

	async function toggle() {
		if (state.value === "idle") await start();
		else if (state.value === "recording") stop();
	}

	onUnmounted(() => {
		cancel();
	});

	return { state, elapsed, toggle, cancel };
}
