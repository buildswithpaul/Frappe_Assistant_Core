/**
 * Robot mood store — central state for the FACO robot's facial expression.
 *
 * The robot has seven moods. At any moment, one is "active" and is what the
 * prominent (welcome / nav header / loading) robot renders. Per-message
 * avatars in chat history are static — they freeze the mood the message was
 * sent with, so a "thanks" reply keeps a delighted face forever.
 *
 * Mood resolution priority (highest wins):
 *   concerned > thinking > delighted (transient) > excited (transient)
 *   > attentive > sleepy > idle
 *
 * Setters from elsewhere in the app:
 *   setStreaming(bool)         chatStore — thinking
 *   setAwaitingApproval(bool)  chat surfaces — concerned
 *   setHasError(bool)          chat error events — concerned
 *   pulseDelighted()           response landed / "thanks" — 1.5s grin
 *   pulseExcited()             first message of a session — 1.5s spark
 *   setAttentive(bool)         InputArea focus — attentive
 *
 * Cursor tracking (eyeX, eyeY in [-1, 1]) is read by the prominent robot
 * when its `track` prop is set. We compute it once globally rather than
 * per-instance so multiple visible robots don't each install mousemove
 * listeners.
 */

import { defineStore } from "pinia";
import { ref, computed } from "vue";

const PULSE_DURATION_MS = 1500;
const SLEEPY_HOUR_START = 23; // 11pm
const SLEEPY_HOUR_END = 5; // 5am

export const useRobotMoodStore = defineStore("robotMood", () => {
	// Continuous signals
	const isStreaming = ref(false);
	const isAttentive = ref(false);
	const isAwaitingApproval = ref(false);
	const hasError = ref(false);

	// Transient pulses
	const delightedUntil = ref(0);
	const excitedUntil = ref(0);

	// Cursor tracking — populated by the global mousemove handler
	const eyeX = ref(0);
	const eyeY = ref(0);

	// Idle hint for sleepy (only matters if currently in idle and night-time)
	const reducedMotion = ref(
		typeof window !== "undefined" &&
			window.matchMedia &&
			window.matchMedia("(prefers-reduced-motion: reduce)").matches
	);

	const now = ref(Date.now());
	const _tickHandle = ref(null);

	function _ensureClock() {
		if (_tickHandle.value || typeof window === "undefined") return;
		_tickHandle.value = window.setInterval(() => {
			now.value = Date.now();
		}, 250);
	}

	function _isNightTime() {
		const h = new Date(now.value).getHours();
		return h >= SLEEPY_HOUR_START || h < SLEEPY_HOUR_END;
	}

	const activeMood = computed(() => {
		if (hasError.value || isAwaitingApproval.value) return "concerned";
		if (isStreaming.value) return "thinking";
		if (now.value < delightedUntil.value) return "delighted";
		if (now.value < excitedUntil.value) return "excited";
		if (isAttentive.value) return "attentive";
		if (_isNightTime()) return "sleepy";
		return "idle";
	});

	function setStreaming(value) {
		_ensureClock();
		isStreaming.value = !!value;
	}

	function setAttentive(value) {
		_ensureClock();
		isAttentive.value = !!value;
	}

	function setAwaitingApproval(value) {
		_ensureClock();
		isAwaitingApproval.value = !!value;
	}

	function setHasError(value) {
		_ensureClock();
		hasError.value = !!value;
	}

	function pulseDelighted() {
		_ensureClock();
		delightedUntil.value = Date.now() + PULSE_DURATION_MS;
	}

	function pulseExcited() {
		_ensureClock();
		excitedUntil.value = Date.now() + PULSE_DURATION_MS;
	}

	function setEyeOffset(x, y) {
		// Clamp to roughly the eye-white travel range (~1.5px each direction)
		const clampedX = Math.max(-1.5, Math.min(1.5, x));
		const clampedY = Math.max(-1.5, Math.min(1.5, y));
		eyeX.value = clampedX;
		eyeY.value = clampedY;
	}

	return {
		// state
		isStreaming,
		isAttentive,
		isAwaitingApproval,
		hasError,
		delightedUntil,
		excitedUntil,
		eyeX,
		eyeY,
		reducedMotion,
		// computed
		activeMood,
		// actions
		setStreaming,
		setAttentive,
		setAwaitingApproval,
		setHasError,
		pulseDelighted,
		pulseExcited,
		setEyeOffset,
	};
});
