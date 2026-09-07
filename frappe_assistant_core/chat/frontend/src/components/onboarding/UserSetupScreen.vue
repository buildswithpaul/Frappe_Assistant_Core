<template>
	<div class="user-setup-container">
		<!-- Setup Flow: admins (first connect) and seated members not yet ready -->
		<template v-if="userStore.isAdmin || isPendingMember">
			<!-- Robot Avatar — friendly wave; mood reflects auth state. -->
			<FacoRobot
				size="lg"
				float
				show-arms
				show-shadow
				:mood="isConnecting ? 'thinking' : error ? 'concerned' : 'attentive'"
				extra-class="mb-6"
			/>

			<!-- Title -->
			<h1 class="setup-title">Connect your account</h1>
			<p class="setup-subtitle">
				Your site is ready. Link your account so FAC can work with the
				documents and permissions you already have.
			</p>

			<!-- Benefits Card -->
			<div class="benefits-card">
				<div class="benefits-title">What you get:</div>
				<div class="benefit-item">
					<div class="benefit-icon check-icon">
						<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M5 13l4 4L19 7"
							/>
						</svg>
					</div>
					<span>Read documents you can already access</span>
				</div>
				<div class="benefit-item">
					<div class="benefit-icon check-icon">
						<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M5 13l4 4L19 7"
							/>
						</svg>
					</div>
					<span>Create or update only with your approval</span>
				</div>
				<div class="benefit-item">
					<div class="benefit-icon check-icon">
						<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M5 13l4 4L19 7"
							/>
						</svg>
					</div>
					<span>Your role permissions are always respected</span>
				</div>
			</div>

			<!-- Error Message -->
			<div v-if="error" class="error-card">
				<div class="error-icon">
					<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
						/>
					</svg>
				</div>
				<p class="error-text">{{ error }}</p>
				<a v-if="tenantOwner" :href="`mailto:${tenantOwner}`" class="owner-link">
					Contact {{ tenantOwner }}
				</a>
			</div>

			<!-- Connect Button -->
			<button class="connect-btn" @click="handleConnect" :disabled="isConnecting">
				<svg v-if="isConnecting" class="spinner" viewBox="0 0 24 24">
					<circle
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="3"
						fill="none"
						opacity="0.25"
					/>
					<path
						d="M12 2a10 10 0 0 1 10 10"
						stroke="currentColor"
						stroke-width="3"
						fill="none"
						stroke-linecap="round"
					/>
				</svg>
				<span v-else>Connect Account</span>
			</button>

			<!-- Security Note -->
			<div class="security-note">
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24" class="lock-icon">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
					/>
				</svg>
				<span
					>Credentials stay on your site and are only used when you ask FAC to take an
					action.</span
				>
			</div>
		</template>

		<!-- Non-Admin Pending Setup -->
		<template v-else>
			<FacoRobot size="lg" show-arms mood="sleepy" extra-class="mb-6" />

			<h1 class="setup-title">Account Pending Setup</h1>
			<p class="setup-subtitle">
				Your administrator needs to add you to FACO.<br />
				Please ask them to add your account from <strong>Settings &gt; Users</strong>.
			</p>

			<div class="pending-card">
				<svg class="pending-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				<div class="pending-text">
					<strong>Waiting for admin setup</strong>
					<span>You'll be able to use FACO once your admin adds you.</span>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useUserStore } from "@/stores/userStore";
import FacoRobot from "@/components/common/FacoRobot.vue";

const emit = defineEmits(["connected"]);

const userStore = useUserStore();

const isPendingMember = computed(
	() => userStore.userAuthStatus?.user_registered && !userStore.userAuthStatus?.ready,
);

const isConnecting = ref(false);
const error = ref(null);
// When AR blocks a non-owner from connecting, it surfaces the tenant
// owner's email so we can render a "Contact <email>" mailto link in the
// error card instead of the generic "contact your administrator".
const tenantOwner = ref(null);

async function handleConnect() {
	isConnecting.value = true;
	error.value = null;
	tenantOwner.value = null;

	try {
		const result = await userStore.connectAccount();

		if (result.success) {
			// Skip the redundant success flash — FeatureTour opens next.
			emit("connected");
		} else {
			error.value = result.error || "Failed to connect. Please try again.";
			tenantOwner.value = result.tenantOwnerUserId || null;
		}
	} catch (err) {
		error.value = getErrorMessage(err);
	} finally {
		isConnecting.value = false;
	}
}

function getErrorMessage(err) {
	const message = err.message || "";

	if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
		return "Can't reach FAC Cloud. Check your internet connection and try again.";
	}
	if (message.includes("timeout") || message.includes("Timeout")) {
		return "Connection timed out. Please try again.";
	}
	if (message.includes("401") || message.includes("403")) {
		return "Authentication failed. Please refresh and try again.";
	}

	return message || "Failed to connect. Please try again.";
}
</script>

<style scoped>
.user-setup-container {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	padding: 2rem;
	text-align: center;
}

.setup-title {
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.setup-subtitle {
	font-size: 1rem;
	color: var(--ql-text-muted);
	margin-bottom: 1.5rem;
	max-width: 400px;
	line-height: 1.5;
}

/* Benefits Card */
.benefits-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.25rem;
	max-width: 380px;
	width: 100%;
	margin-bottom: 1.5rem;
}

.benefits-title {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
	text-align: left;
}

.benefit-item {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
	text-align: left;
}

.benefit-item:last-child {
	margin-bottom: 0;
}

.benefit-icon {
	flex-shrink: 0;
	width: 1.25rem;
	height: 1.25rem;
}

.check-icon {
	color: var(--ql-success);
}

.benefit-icon svg {
	width: 100%;
	height: 100%;
}

/* Connect Button */
.connect-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 0.875rem 2rem;
	font-size: 1rem;
	font-weight: 600;
	color: white;
	background: linear-gradient(135deg, var(--ql-accent) 0%, var(--ql-accent-hover) 100%);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.2s ease;
	min-width: 240px;
	margin-bottom: 1rem;
}

.connect-btn:hover:not(:disabled) {
	transform: translateY(-1px);
	box-shadow: 0 4px 12px var(--ql-accent-soft);
}

.connect-btn:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

.spinner {
	width: 1.25rem;
	height: 1.25rem;
	animation: spin 1s linear infinite;
}

@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

/* Security Note */
.security-note {
	display: flex;
	align-items: flex-start;
	gap: 0.5rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	max-width: 340px;
	text-align: left;
}

.lock-icon {
	flex-shrink: 0;
	width: 1rem;
	height: 1rem;
	margin-top: 0.1rem;
}

/* Pending Setup (non-admin) */
.pending-card {
	display: flex;
	align-items: flex-start;
	gap: 0.75rem;
	padding: 1rem 1.25rem;
	background: rgba(245, 158, 11, 0.06);
	border: 1px solid rgba(245, 158, 11, 0.2);
	border-radius: 0.75rem;
	max-width: 380px;
	margin-top: 1.25rem;
}

.pending-icon {
	width: 1.25rem;
	height: 1.25rem;
	color: var(--ql-warning);
	flex-shrink: 0;
	margin-top: 0.125rem;
}

.pending-text {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.pending-text span {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

/* Error Card */
.error-card {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 1rem 1.5rem;
	background: rgba(239, 68, 68, 0.08);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.75rem;
	max-width: 380px;
	width: 100%;
	margin-bottom: 1rem;
}

.error-card .error-icon {
	width: 2rem;
	height: 2rem;
	color: var(--ql-danger);
}

.error-card .error-icon svg {
	width: 100%;
	height: 100%;
}

.error-text {
	font-size: 0.875rem;
	color: var(--ql-danger);
	text-align: center;
	line-height: 1.4;
	word-break: break-word;
	overflow-wrap: anywhere;
	max-width: 100%;
}

.owner-link {
	display: inline-block;
	margin-top: 0.25rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-accent);
	text-decoration: none;
	word-break: break-all;
}

.owner-link:hover {
	text-decoration: underline;
}

/* Success State */
.success-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	animation: success-fade-in 0.5s ease;
}

.success-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
	margin-top: 1.5rem;
}

.success-icon {
	width: 3rem;
	height: 3rem;
	color: var(--ql-success);
	background: rgba(34, 197, 94, 0.1);
	border-radius: 50%;
	padding: 0.5rem;
	animation: success-pop 0.5s ease 0.2s both;
}

.success-icon svg {
	width: 100%;
	height: 100%;
}

.success-title {
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-success);
	animation: success-slide-up 0.5s ease 0.3s both;
}

.success-message {
	font-size: 1rem;
	color: var(--ql-text-muted);
	animation: success-slide-up 0.5s ease 0.4s both;
}

/* Robot celebrate animation — preserves the .faco-robot-lg base scale(1.2).
   Without multiplying through 1.2 the keyframes would override the base
   transform and the robot would visibly shrink mid-animation. */
.robot-celebrate {
	animation: robot-celebrate 1s ease-in-out;
}

@keyframes robot-celebrate {
	0%,
	100% {
		transform: scale(1.2) rotate(0deg);
	}
	25% {
		transform: scale(1.32) rotate(-5deg);
	}
	50% {
		transform: scale(1.38) rotate(5deg);
	}
	75% {
		transform: scale(1.32) rotate(-3deg);
	}
}

@keyframes success-fade-in {
	from {
		opacity: 0;
	}
	to {
		opacity: 1;
	}
}

@keyframes success-pop {
	from {
		transform: scale(0);
		opacity: 0;
	}
	to {
		transform: scale(1);
		opacity: 1;
	}
}

@keyframes success-slide-up {
	from {
		transform: translateY(20px);
		opacity: 0;
	}
	to {
		transform: translateY(0);
		opacity: 1;
	}
}

/* Responsive */
@media (max-width: 640px) {
	.user-setup-container {
		padding: 1.5rem;
	}

	.setup-title {
		font-size: 1.5rem;
	}

	.benefits-card {
		padding: 1rem;
	}
}
</style>
