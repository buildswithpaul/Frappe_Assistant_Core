<template>
	<div class="privacy-settings">
		<!-- User Section: Your Privacy -->
		<h3 class="section-title">Your Privacy</h3>

		<div v-if="zeroRetention" class="setting-item">
			<div class="setting-info">
				<label class="setting-label">Zero Retention</label>
				<p class="setting-description">
					Your conversations are stored only on this site — they never persist on
					our servers.
				</p>
			</div>
			<span class="status-badge status-on">On</span>
		</div>

		<div v-if="memoryEnabled" class="setting-item">
			<div class="setting-info">
				<label class="setting-label">AI Memory</label>
				<p class="setting-description">
					Allow FACO to learn from your conversations and remember your preferences
				</p>
			</div>
			<label class="toggle">
				<input type="checkbox" v-model="memoryConsent" @change="toggleMemoryConsent" />
				<span class="toggle-slider"></span>
			</label>
		</div>

		<div class="setting-item">
			<div class="setting-info">
				<label class="setting-label">Restrict data processing</label>
				<p class="setting-description">
					Pause memory extraction and retrieval while keeping your data intact
				</p>
			</div>
			<label class="toggle">
				<input
					type="checkbox"
					v-model="processingRestricted"
					@change="toggleRestriction"
				/>
				<span class="toggle-slider"></span>
			</label>
		</div>

		<hr class="divider" />

		<h3 class="section-title">Your Data</h3>

		<div class="setting-item">
			<div class="setting-info">
				<label class="setting-label">Download your data</label>
				<p class="setting-description">Export all your data as a JSON file</p>
			</div>
			<button @click="exportData" :disabled="exporting" class="action-btn">
				{{ exporting ? "Exporting..." : "Download" }}
			</button>
		</div>

		<div class="setting-item">
			<div class="setting-info">
				<label class="setting-label">Archive all conversations</label>
				<p class="setting-description">
					Remove conversations from our servers while keeping a local copy on your
					instance
				</p>
			</div>
			<button @click="archiveAll" :disabled="clearing" class="danger-btn">
				{{ clearing ? "Archiving..." : "Archive All" }}
			</button>
		</div>

		<div class="setting-item">
			<div class="setting-info">
				<label class="setting-label">Delete all my data</label>
				<p class="setting-description">
					Permanently erase all data — both local and cloud. This cannot be undone.
				</p>
			</div>
			<button @click="showEraseConfirm = true" class="danger-btn danger-btn-filled">
				Delete Everything
			</button>
		</div>

		<!-- Privacy contact -->
		<div v-if="privacyContactEmail" class="privacy-contact">
			Questions about your data? Contact
			<a :href="'mailto:' + privacyContactEmail">{{ privacyContactEmail }}</a>
		</div>

		<!-- Erase Confirmation Dialog -->
		<Teleport to="body">
			<div
				v-if="showEraseConfirm"
				class="dialog-overlay"
				@click.self="showEraseConfirm = false"
			>
				<div class="dialog-box">
					<h3 class="dialog-title">Delete All Data</h3>
					<p class="dialog-text">
						This will permanently delete all your conversations, messages, memories,
						documents, and profile data. This action cannot be undone.
					</p>
					<p class="dialog-text">Enter your password to confirm:</p>
					<input
						v-model="erasePassword"
						type="password"
						class="dialog-input"
						placeholder="Your password"
						@keyup.enter="eraseAllData"
					/>
					<div class="dialog-actions">
						<button @click="showEraseConfirm = false" class="dialog-cancel">
							Cancel
						</button>
						<button
							@click="eraseAllData"
							:disabled="!erasePassword || erasing"
							class="dialog-confirm"
						>
							{{ erasing ? "Deleting..." : "Delete Everything" }}
						</button>
					</div>
				</div>
			</div>
		</Teleport>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { storeToRefs } from "pinia";
import { api } from "@/api/client";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { logger } from "@/utils/logger";

const emit = defineEmits(["notification"]);

const chatStore = useChatStore();
const userStore = useUserStore();

// Live ref — zeroRetention is set asynchronously by the stream_start socket
// handler, so it must stay reactive (not a one-time snapshot).
const { zeroRetention } = storeToRefs(userStore);
const memoryEnabled = ref(userStore.memoryEnabled);
const processingRestricted = ref(false);
const memoryConsent = ref(false);
const exporting = ref(false);
const clearing = ref(false);
const erasing = ref(false);
const showEraseConfirm = ref(false);
const erasePassword = ref("");
const privacyContactEmail = ref("");

onMounted(async () => {
	try {
		const config = await api.privacy.getConfig();
		if (config) {
			if (config.tenant) {
				privacyContactEmail.value = config.tenant.privacy_contact_email || "";
			}
			if (config.user_privacy) {
				memoryConsent.value = config.user_privacy.memory_consent || false;
				processingRestricted.value = config.user_privacy.processing_restricted || false;
			}
		}
	} catch (err) {
		logger.error("Failed to load privacy config:", err);
	}
});

async function exportData() {
	exporting.value = true;
	try {
		const result = await api.privacy.exportData();
		if (result && result.data) {
			const blob = new Blob([JSON.stringify(result.data, null, 2)], {
				type: "application/json",
			});
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = `my-data-export-${new Date().toISOString().slice(0, 10)}.json`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			emit("notification", { message: "Data exported successfully", type: "success" });
		}
	} catch (err) {
		logger.error("Failed to export data:", err);
		emit("notification", { message: "Failed to export data", type: "error" });
	} finally {
		exporting.value = false;
	}
}

async function archiveAll() {
	if (
		!confirm(
			"Archive all conversations? They will be removed from our servers but kept locally on your instance."
		)
	) {
		return;
	}
	clearing.value = true;
	try {
		await api.chat.archiveAllConversations();
		chatStore.clearSessions();
		emit("notification", { message: "All conversations archived", type: "success" });
	} catch (err) {
		logger.error("Failed to archive conversations:", err);
		emit("notification", { message: "Failed to archive conversations", type: "error" });
	} finally {
		clearing.value = false;
	}
}

async function eraseAllData() {
	if (!erasePassword.value) return;
	erasing.value = true;
	try {
		await api.privacy.eraseData(erasePassword.value);
		chatStore.clearSessions();
		showEraseConfirm.value = false;
		erasePassword.value = "";
		emit("notification", { message: "All data deleted successfully", type: "success" });
	} catch (err) {
		logger.error("Failed to erase data:", err);
		emit("notification", {
			message: err.message || "Failed to delete data. Check your password.",
			type: "error",
		});
	} finally {
		erasing.value = false;
	}
}

async function toggleRestriction() {
	try {
		await api.privacy.restrictProcessing(processingRestricted.value);
		const status = processingRestricted.value ? "restricted" : "unrestricted";
		emit("notification", { message: `Data processing ${status}`, type: "success" });
	} catch (err) {
		processingRestricted.value = !processingRestricted.value;
		logger.error("Failed to update restriction:", err);
		emit("notification", {
			message: "Failed to update processing restriction",
			type: "error",
		});
	}
}

async function toggleMemoryConsent() {
	try {
		await api.privacy.updateConsent("memory", memoryConsent.value);
		const status = memoryConsent.value ? "granted" : "withdrawn";
		emit("notification", { message: `Memory consent ${status}`, type: "success" });
	} catch (err) {
		memoryConsent.value = !memoryConsent.value;
		logger.error("Failed to update consent:", err);
		emit("notification", { message: "Failed to update memory consent", type: "error" });
	}
}
</script>

<style scoped>
.privacy-settings {
	width: 100%;
	max-width: 1100px;
}

.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 1rem;
}

.setting-item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 0.75rem 0;
}

.status-badge {
	display: inline-flex;
	align-items: center;
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	border-radius: 9999px;
	flex-shrink: 0;
}

.status-badge.status-on {
	background: rgba(34, 197, 94, 0.1);
	color: #16a34a;
}

.setting-info {
	flex: 1;
	min-width: 0;
	margin-right: 1rem;
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

.action-btn {
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: none;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.action-btn:hover:not(:disabled) {
	background: var(--ql-accent-soft);
}

.action-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.danger-btn {
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: #ef4444;
	background: none;
	border: 1px solid #ef4444;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.danger-btn:hover:not(:disabled) {
	background: rgba(239, 68, 68, 0.1);
}

.danger-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.danger-btn-filled {
	color: white;
	background: #ef4444;
}

.danger-btn-filled:hover:not(:disabled) {
	background: #dc2626;
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

.privacy-contact {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin-top: 1rem;
	padding-top: 0.75rem;
	border-top: 1px solid var(--ql-border);
}

.privacy-contact a {
	color: var(--ql-accent);
	text-decoration: none;
}

.privacy-contact a:hover {
	text-decoration: underline;
}

.divider {
	border: none;
	border-top: 1px solid var(--ql-border);
	margin: 1rem 0;
}

/* Erase confirmation dialog */
.dialog-overlay {
	position: fixed;
	inset: 0;
	z-index: 1100;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: rgba(0, 0, 0, 0.5);
	backdrop-filter: blur(4px);
}

.dialog-box {
	background: var(--ql-surface);
	border-radius: 0.75rem;
	padding: 1.5rem;
	max-width: 420px;
	width: 90%;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.dialog-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: #ef4444;
	margin-bottom: 0.75rem;
}

.dialog-text {
	font-size: 0.875rem;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
	line-height: 1.5;
}

.dialog-input {
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-bg);
	color: var(--ql-text);
	margin-bottom: 1rem;
}

.dialog-input:focus {
	outline: none;
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.dialog-actions {
	display: flex;
	gap: 0.5rem;
	justify-content: flex-end;
}

.dialog-cancel {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}

.dialog-confirm {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background: #ef4444;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.dialog-confirm:hover:not(:disabled) {
	background: #dc2626;
}

.dialog-confirm:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
