// Frappe Assistant Copilot - Voice Capture Module
// Copyright (C) 2025 Paul Clinton
// AGPL-3.0 License

/**
 * FACO Voice Capture
 *
 * Owns the MediaRecorder lifecycle and emits high-level events for the
 * UI to consume. Public API:
 *
 *   const capture = new FACOVoiceCapture({
 *     onStateChange(state)   // 'idle' | 'requesting' | 'recording' | 'transcribing' | 'error'
 *     onElapsed(seconds)     // every 100ms during recording
 *     onComplete(audioBlob, durationMs)
 *     onError(reason, code)  // 'permission-denied' | 'no-mic' | 'recorder-error' | 'too-short'
 *   });
 *   capture.toggle();   // tap-to-start / tap-to-stop
 *   capture.cancel();   // hard-cancel without firing onComplete
 *
 * Hard cap: 60 seconds. Auto-stops + auto-fires onComplete.
 * Sub-1-second recordings fire onError('too-short') and discard audio.
 */
window.FACOVoiceCapture = class {
	static MAX_SECONDS = 60;
	static MIN_SECONDS = 1.0;
	static TICK_MS = 100;

	constructor(handlers = {}) {
		this.onStateChange = handlers.onStateChange || (() => {});
		this.onElapsed = handlers.onElapsed || (() => {});
		this.onComplete = handlers.onComplete || (() => {});
		this.onError = handlers.onError || (() => {});

		this._state = "idle";
		this._mediaRecorder = null;
		this._stream = null;
		this._chunks = [];
		this._startedAt = 0;
		this._tickInterval = null;
		this._hardCapTimer = null;
		this._visibilityHandler = null;
	}

	get state() {
		return this._state;
	}

	_setState(next) {
		this._state = next;
		this.onStateChange(next);
	}

	async toggle() {
		if (this._state === "idle") {
			await this._start();
		} else if (this._state === "recording") {
			this._stop();
		}
		// In other states (requesting, transcribing, error), toggle is a no-op.
	}

	async _start() {
		this._setState("requesting");

		try {
			this._stream = await navigator.mediaDevices.getUserMedia({ audio: true });
		} catch (err) {
			this._setState("error");
			const code = err.name === "NotAllowedError" ? "permission-denied" : "no-mic";
			this.onError(err.message || String(err), code);
			setTimeout(() => this._setState("idle"), 0);
			return;
		}

		const mime = this._pickMimeType();

		try {
			this._mediaRecorder = new MediaRecorder(this._stream, { mimeType: mime });
		} catch (err) {
			this._cleanupStream();
			this._setState("error");
			this.onError(err.message || String(err), "recorder-error");
			setTimeout(() => this._setState("idle"), 0);
			return;
		}

		this._chunks = [];
		this._mediaRecorder.ondataavailable = (e) => {
			if (e.data && e.data.size > 0) this._chunks.push(e.data);
		};
		this._mediaRecorder.onstop = () => this._handleStop(mime);
		this._mediaRecorder.onerror = (e) => {
			this._cleanupStream();
			this._setState("error");
			this.onError(e.error?.message || "recorder error", "recorder-error");
			setTimeout(() => this._setState("idle"), 0);
		};

		this._startedAt = Date.now();
		this._mediaRecorder.start();
		this._setState("recording");

		this._tickInterval = setInterval(() => {
			const elapsed = (Date.now() - this._startedAt) / 1000;
			this.onElapsed(elapsed);
		}, FACOVoiceCapture.TICK_MS);

		this._hardCapTimer = setTimeout(() => {
			if (this._state === "recording") this._stop();
		}, FACOVoiceCapture.MAX_SECONDS * 1000);

		this._visibilityHandler = () => {
			if (document.hidden && this._state === "recording") this.cancel();
		};
		document.addEventListener("visibilitychange", this._visibilityHandler);
	}

	_stop() {
		if (!this._mediaRecorder || this._mediaRecorder.state === "inactive") return;
		this._mediaRecorder.stop();
	}

	cancel() {
		this._chunks = [];
		if (this._mediaRecorder && this._mediaRecorder.state !== "inactive") {
			this._mediaRecorder.stop();
		}
		this._cleanupTimers();
		this._cleanupStream();
		this._setState("idle");
	}

	_handleStop(mime) {
		this._cleanupTimers();
		this._cleanupStream();

		const durationMs = Date.now() - this._startedAt;
		const durationSec = durationMs / 1000;

		if (durationSec < FACOVoiceCapture.MIN_SECONDS) {
			this._setState("error");
			this.onError("Recording too short", "too-short");
			setTimeout(() => this._setState("idle"), 0);
			return;
		}

		if (this._chunks.length === 0) {
			this._setState("error");
			this.onError("No audio captured", "recorder-error");
			setTimeout(() => this._setState("idle"), 0);
			return;
		}

		const blob = new Blob(this._chunks, { type: mime });
		this._setState("transcribing");
		this.onComplete(blob, durationMs);
	}

	_pickMimeType() {
		const candidates = [
			"audio/webm;codecs=opus",
			"audio/webm",
			"audio/mp4",
			"audio/ogg;codecs=opus",
		];
		for (const c of candidates) {
			if (window.MediaRecorder && MediaRecorder.isTypeSupported(c)) return c;
		}
		return "audio/webm";
	}

	_cleanupTimers() {
		if (this._tickInterval) {
			clearInterval(this._tickInterval);
			this._tickInterval = null;
		}
		if (this._hardCapTimer) {
			clearTimeout(this._hardCapTimer);
			this._hardCapTimer = null;
		}
		if (this._visibilityHandler) {
			document.removeEventListener("visibilitychange", this._visibilityHandler);
			this._visibilityHandler = null;
		}
	}

	_cleanupStream() {
		if (this._stream) {
			this._stream.getTracks().forEach((t) => t.stop());
			this._stream = null;
		}
	}

	/** Mark transition out of `transcribing` (called by the UI after the network call completes). */
	finishedTranscribing() {
		if (this._state === "transcribing") this._setState("idle");
	}
};
