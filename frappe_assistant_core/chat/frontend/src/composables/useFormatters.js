/**
 * Shared formatting utilities used across FACO SPA components.
 *
 * Consolidates duplicate formatDate / formatFileSize / formatTokens
 * implementations that were previously scattered across 5+ files.
 */

/**
 * Format a date string as a short absolute date (e.g. "Feb 22, 2026").
 * Used by billing invoices, terms modal, etc.
 */
export function formatDate(dateStr) {
	if (!dateStr) return "--";
	try {
		return new Date(dateStr).toLocaleDateString("en-US", {
			month: "short",
			day: "numeric",
			year: "numeric",
		});
	} catch {
		return dateStr;
	}
}

/**
 * Format a date string as a long absolute date (e.g. "February 22, 2026").
 * Used by terms modal effective date.
 */
export function formatDateLong(dateStr) {
	if (!dateStr) return "--";
	try {
		return new Date(dateStr).toLocaleDateString("en-US", {
			year: "numeric",
			month: "long",
			day: "numeric",
		});
	} catch {
		return dateStr;
	}
}

/**
 * Format a date string as relative time (e.g. "5m ago", "2d ago").
 * Falls back to short date for older dates. Used by document cards,
 * workflow cards, navigation sidebar session list.
 */
export function formatRelativeTime(dateStr) {
	if (!dateStr) return "";
	const date = new Date(dateStr);
	if (isNaN(date.getTime())) return "";

	const now = new Date();
	const diffMs = now - date;
	const diffMins = Math.floor(diffMs / 60000);
	const diffHours = Math.floor(diffMs / 3600000);
	const diffDays = Math.floor(diffMs / 86400000);

	if (diffMins < 1) return "Just now";
	if (diffMins < 60) return `${diffMins}m ago`;
	if (diffHours < 24) return `${diffHours}h ago`;
	if (diffDays < 7) return `${diffDays}d ago`;

	return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Format credit / token counts for user-facing display.
 * Rounds to whole numbers below 1K (avoids "60.874000000000024" raw-float
 * artefacts in quota displays); uses K/M suffixes beyond that.
 */
export function formatTokens(num) {
	const n = Number(num) || 0;
	if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
	if (n >= 1000) return Math.round(n / 1000) + "K";
	return Math.round(n).toLocaleString();
}

// Credits and tokens use the same formatting (K/M suffixes + rounding).
// Exported under a credits-named alias so call sites can read clearly:
// `formatCredits(balance)` reads better in user-facing components than
// `formatTokens(balance)`.
export const formatCredits = formatTokens;

/**
 * Format currency amount using Intl.NumberFormat.
 * @param {number} amount - The numeric amount
 * @param {string} currency - ISO 4217 currency code (default: 'USD')
 */
export function formatCurrency(amount, currency = "USD") {
	if (typeof amount !== "number") return amount;
	return new Intl.NumberFormat("en-US", {
		style: "currency",
		currency,
		minimumFractionDigits: 0,
		maximumFractionDigits: 2,
	}).format(amount);
}

/**
 * Format file size from bytes (e.g. 1024 → "1.0 KB", 5242880 → "5.0 MB").
 * Used by InputArea for upload previews.
 */
export function formatFileSize(bytes) {
	if (bytes < 1024) return bytes + " B";
	if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
	return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

/**
 * Format file size from megabytes (e.g. 0.005 → "< 0.01 MB", 2.5 → "2.50 MB").
 * Used by KnowledgeBase document cards.
 */
export function formatFileSizeMb(sizeMb) {
	if (!sizeMb && sizeMb !== 0) return "";
	if (sizeMb < 0.01) return "< 0.01 MB";
	return sizeMb.toFixed(2) + " MB";
}

/**
 * Format megabytes with auto-scale to GB (e.g. 500 → "500.0 MB", 1500 → "1.5 GB").
 * Used by KnowledgeBase storage bar.
 */
export function formatStorageSize(mb) {
	if (!mb && mb !== 0) return "0 MB";
	if (mb >= 1024) return (mb / 1024).toFixed(1) + " GB";
	if (mb < 1) return mb.toFixed(2) + " MB";
	return mb.toFixed(1) + " MB";
}

/**
 * Capitalize and normalize plan name (e.g. "development" → "Dev", "pro" → "Pro").
 */
export function formatPlanName(plan) {
	if (!plan) return "Free";
	const name = plan.charAt(0).toUpperCase() + plan.slice(1).toLowerCase();
	return name === "Development" ? "Dev" : name;
}
