/**
 * Composable for managing user profile data.
 *
 * Handles loading, saving, and dirty-checking for the Profile settings tab.
 * Profile fields are stored on AR Tenant User and injected into the AI system prompt.
 */

import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

export function useProfileData() {
	// State
	const loading = ref(true);
	const saving = ref(false);
	const error = ref(null);
	const successMessage = ref(null);

	// Form fields (current values)
	const displayName = ref("");
	const jobTitle = ref("");
	const department = ref("");
	const about = ref("");
	const customInstructions = ref("");
	const locale = ref("");
	const timezone = ref("");

	// Original values (for dirty-checking)
	const _original = ref({});

	// Computed
	const isDirty = computed(() => {
		const o = _original.value;
		return (
			displayName.value !== (o.displayName || "") ||
			jobTitle.value !== (o.jobTitle || "") ||
			department.value !== (o.department || "") ||
			about.value !== (o.about || "") ||
			customInstructions.value !== (o.customInstructions || "") ||
			locale.value !== (o.locale || "") ||
			timezone.value !== (o.timezone || "")
		);
	});

	const aboutLength = computed(() => about.value.length);

	// Load profile from backend
	async function loadProfile() {
		loading.value = true;
		error.value = null;
		try {
			const data = await api.profile.get();
			if (data) {
				displayName.value = data.display_name || "";
				jobTitle.value = data.job_title || "";
				department.value = data.department || "";
				about.value = data.about || "";
				customInstructions.value = data.custom_instructions || "";
				locale.value = data.locale || "";
				timezone.value = data.timezone || "";

				_original.value = {
					displayName: data.display_name || "",
					jobTitle: data.job_title || "",
					department: data.department || "",
					about: data.about || "",
					customInstructions: data.custom_instructions || "",
					locale: data.locale || "",
					timezone: data.timezone || "",
				};
			}
		} catch (err) {
			error.value = err.message || "Failed to load profile";
			logger.error("Profile load error:", err);
		} finally {
			loading.value = false;
		}
	}

	// Reset every field to the last saved values. No API call — _original is
	// already the server's copy, refreshed on load and after each save.
	function discardChanges() {
		const o = _original.value;
		displayName.value = o.displayName || "";
		jobTitle.value = o.jobTitle || "";
		department.value = o.department || "";
		about.value = o.about || "";
		customInstructions.value = o.customInstructions || "";
		locale.value = o.locale || "";
		timezone.value = o.timezone || "";
		error.value = null;
		successMessage.value = null;
	}

	// Save only changed fields
	async function saveProfile() {
		if (!isDirty.value) return;

		saving.value = true;
		error.value = null;
		successMessage.value = null;

		const o = _original.value;
		const fields = {};

		if (displayName.value !== (o.displayName || "")) fields.display_name = displayName.value;
		if (jobTitle.value !== (o.jobTitle || "")) fields.job_title = jobTitle.value;
		if (department.value !== (o.department || "")) fields.department = department.value;
		if (about.value !== (o.about || "")) fields.about = about.value;
		if (customInstructions.value !== (o.customInstructions || ""))
			fields.custom_instructions = customInstructions.value;
		if (locale.value !== (o.locale || "")) fields.locale = locale.value;
		if (timezone.value !== (o.timezone || "")) fields.timezone = timezone.value;

		try {
			await api.profile.update(fields);

			// Update originals to match current
			_original.value = {
				displayName: displayName.value,
				jobTitle: jobTitle.value,
				department: department.value,
				about: about.value,
				customInstructions: customInstructions.value,
				locale: locale.value,
				timezone: timezone.value,
			};

			successMessage.value = "Profile saved";
			setTimeout(() => {
				successMessage.value = null;
			}, 3000);
		} catch (err) {
			error.value = err.message || "Failed to save profile";
			logger.error("Profile save error:", err);
		} finally {
			saving.value = false;
		}
	}

	return {
		// State
		loading,
		saving,
		error,
		successMessage,
		displayName,
		jobTitle,
		department,
		about,
		customInstructions,
		locale,
		timezone,
		// Computed
		isDirty,
		aboutLength,
		// Actions
		loadProfile,
		saveProfile,
		discardChanges,
	};
}
