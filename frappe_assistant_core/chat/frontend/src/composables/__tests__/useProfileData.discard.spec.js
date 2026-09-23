import { describe, it, expect, vi, beforeEach } from "vitest";

const get = vi.fn();
const update = vi.fn();

vi.mock("@/api/client", () => ({
	api: {
		profile: {
			get: (...args) => get(...args),
			update: (...args) => update(...args),
		},
	},
}));

import { useProfileData } from "../useProfileData";

const SAVED = {
	display_name: "Ada",
	job_title: "Engineering Manager",
	department: "Engineering",
	about: "Runs the platform team",
	custom_instructions: "Prefer tables",
	locale: "en",
	timezone: "Asia/Kolkata",
};

describe("useProfileData — discardChanges", () => {
	beforeEach(() => {
		get.mockReset().mockResolvedValue({ ...SAVED });
		update.mockReset().mockResolvedValue({});
	});

	it("restores every field to the last saved value and clears dirty", async () => {
		const p = useProfileData();
		await p.loadProfile();

		p.displayName.value = "Grace";
		p.jobTitle.value = "";
		p.about.value = "something else entirely";
		p.customInstructions.value = "";
		p.timezone.value = "UTC";
		expect(p.isDirty.value).toBe(true);

		p.discardChanges();

		expect(p.displayName.value).toBe("Ada");
		expect(p.jobTitle.value).toBe("Engineering Manager");
		expect(p.about.value).toBe("Runs the platform team");
		expect(p.customInstructions.value).toBe("Prefer tables");
		expect(p.timezone.value).toBe("Asia/Kolkata");
		expect(p.isDirty.value).toBe(false);
	});

	it("discards back to the newest save, not to the originally loaded values", async () => {
		const p = useProfileData();
		await p.loadProfile();

		p.jobTitle.value = "Director";
		await p.saveProfile();

		p.jobTitle.value = "scribble";
		p.discardChanges();

		expect(p.jobTitle.value).toBe("Director");
		expect(p.isDirty.value).toBe(false);
	});

	it("never calls the API", async () => {
		const p = useProfileData();
		await p.loadProfile();
		update.mockClear();

		p.about.value = "changed";
		p.discardChanges();

		expect(update).not.toHaveBeenCalled();
	});

	it("clears a stale error banner so the form reads as settled", async () => {
		const p = useProfileData();
		await p.loadProfile();
		update.mockRejectedValueOnce(new Error("Network down"));

		p.about.value = "changed";
		await p.saveProfile();
		expect(p.error.value).toBe("Network down");

		p.discardChanges();
		expect(p.error.value).toBe(null);
	});
});
