<template>
	<div class="workspace-settings">
		<RegistrationStatusSection
			:registration-status="userStore.registrationStatus"
			:tenant-id="userStore.quotaInfo?.tenant_id || ''"
			:can-rebind="isSystemManager"
			@open-rebind="showRebindWizard = true"
		/>

		<!-- Admins only: diagnostics + rebind wizard. Both endpoints require
		     System Manager on the backend so we mirror that gate in the UI. -->
		<template v-if="isSystemManager">
			<div class="diagnostics-wrap">
				<RegistrationDiagnostics @open-rebind="showRebindWizard = true" />
			</div>

			<RebindWizard
				:is-open="showRebindWizard"
				@close="showRebindWizard = false"
				@rebound="handleRebound"
			/>
		</template>

		<hr v-if="isSystemManager" class="divider" />

		<section v-if="isSystemManager" class="tenant-policy-section">
			<h3 class="section-title">Tenant Privacy Policy</h3>
			<p class="section-description">
				Configure data privacy defaults for all users on this instance.
			</p>

			<div class="setting-item">
				<div class="setting-info">
					<label class="setting-label">Data retention</label>
					<p class="setting-description">
						How long conversations are kept on the cloud server
					</p>
				</div>
				<select
					v-model="tenantConfig.conversation_retention_days"
					@change="saveTenantConfig"
					class="select-input"
				>
					<option :value="0">Use global default</option>
					<option :value="30">30 days</option>
					<option :value="90">90 days</option>
					<option :value="180">180 days</option>
					<option :value="365">1 year</option>
				</select>
			</div>

			<div class="setting-item">
				<div class="setting-info">
					<label class="setting-label">Default memory consent</label>
					<p class="setting-description">
						<template v-if="tenantConfig.default_memory_consent === 'Opt-Out'">
							Memory enabled by default — users can opt out
						</template>
						<template v-else>
							Memory disabled by default — users must opt in
						</template>
					</p>
				</div>
				<select
					v-model="tenantConfig.default_memory_consent"
					@change="saveTenantConfig"
					class="select-input"
				>
					<option value="Opt-In">Opt-In (users must enable)</option>
					<option value="Opt-Out">Opt-Out (enabled by default)</option>
				</select>
			</div>

			<div class="setting-item">
				<div class="setting-info">
					<label class="setting-label">Privacy contact email</label>
					<p class="setting-description">
						Displayed to users for data protection inquiries
					</p>
				</div>
				<input
					v-model="tenantConfig.privacy_contact_email"
					@blur="saveTenantConfig"
					type="email"
					class="text-input"
					placeholder="dpo@example.com"
				/>
			</div>
		</section>
	</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useUserStore } from "@/stores/userStore";
import { storeToRefs } from "pinia";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import RegistrationStatusSection from "./account/RegistrationStatusSection.vue";
import RegistrationDiagnostics from "./account/RegistrationDiagnostics.vue";
import RebindWizard from "./account/RebindWizard.vue";

const emit = defineEmits(["notification"]);

const showRebindWizard = ref(false);

const userStore = useUserStore();
const { isAdmin } = storeToRefs(userStore);
const isSystemManager = computed(() => isAdmin.value);

const tenantConfig = reactive({
	default_memory_consent: "Opt-In",
	conversation_retention_days: 0,
	privacy_contact_email: "",
});

async function handleRebound() {
	showRebindWizard.value = false;
	await userStore.refreshRegistrationStatus();
}

// Load MCP servers on mount (still consumed elsewhere: workflowStore.js,
// the workflow tool picker, and onboarding all read userStore.mcpServers).
onMounted(async () => {
	if (userStore.registrationStatus === "ready") {
		await userStore.loadMCPServers();
	}

	if (isSystemManager.value) {
		try {
			const config = await api.privacy.getConfig();
			if (config && config.tenant) {
				tenantConfig.default_memory_consent =
					config.tenant.default_memory_consent || "Opt-In";
				tenantConfig.conversation_retention_days =
					config.tenant.conversation_retention_days || 0;
				tenantConfig.privacy_contact_email = config.tenant.privacy_contact_email || "";
			}
		} catch (err) {
			logger.error("Failed to load tenant privacy config:", err);
		}
	}
});

let _tenantSaveTimeout = null;
function saveTenantConfig() {
	clearTimeout(_tenantSaveTimeout);
	_tenantSaveTimeout = setTimeout(async () => {
		try {
			await api.privacy.updateConfig({
				default_memory_consent: tenantConfig.default_memory_consent,
				conversation_retention_days: tenantConfig.conversation_retention_days,
				privacy_contact_email: tenantConfig.privacy_contact_email,
			});
			emit("notification", { message: "Tenant privacy saved", type: "success" });
		} catch (err) {
			logger.error("Failed to save tenant privacy config:", err);
			emit("notification", { message: "Failed to save tenant privacy", type: "error" });
		}
	}, 300);
}
</script>

<style scoped>
.workspace-settings {
	width: 100%;
	max-width: 1100px;
}

.divider {
	border: none;
	border-top: 1px solid var(--ql-border);
	margin: 1.5rem 0;
}

.diagnostics-wrap {
	margin-top: 1.5rem;
}

.tenant-policy-section {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	padding: 24px;
	margin-top: 1.5rem;
	margin-bottom: 24px;
}

.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.section-description {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin-bottom: 1rem;
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

.select-input,
.text-input {
	padding: 0.375rem 0.5rem;
	font-size: 0.8125rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-bg);
	color: var(--ql-text);
	flex-shrink: 0;
}

.text-input {
	width: 200px;
}

.select-input:focus,
.text-input:focus {
	outline: none;
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}
</style>
