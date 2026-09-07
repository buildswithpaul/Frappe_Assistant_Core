/**
 * Whisper-supported languages for voice transcription.
 *
 * Curated subset of Whisper's 99 supported languages, weighted toward:
 *   1. All Indian languages Whisper supports (14 of India's 22 official languages)
 *   2. Every major ERPNext market worldwide (MENA, SE Asia, EU, LatAm, Africa)
 *
 * Each entry:
 *   - code:   ISO-639-1 (lowercase). What we send to Whisper.
 *   - name:   English name (for search + accessibility).
 *   - native: Native-script name (primary label in dropdown).
 *
 * Indian languages Whisper does NOT support yet: Odia, Konkani, Maithili,
 * Bodo, Dogri, Kashmiri, Manipuri, Santali. If your users speak these,
 * they should leave the field blank (Whisper auto-detect) and accept
 * slightly higher hallucination risk on silent clips.
 */

export const WHISPER_LANGUAGES = [
	// ─── Indian subcontinent ──────────────────────────────────────────
	{ code: "hi", name: "Hindi", native: "हिन्दी" },
	{ code: "bn", name: "Bengali", native: "বাংলা" },
	{ code: "ta", name: "Tamil", native: "தமிழ்" },
	{ code: "te", name: "Telugu", native: "తెలుగు" },
	{ code: "mr", name: "Marathi", native: "मराठी" },
	{ code: "gu", name: "Gujarati", native: "ગુજરાતી" },
	{ code: "kn", name: "Kannada", native: "ಕನ್ನಡ" },
	{ code: "ml", name: "Malayalam", native: "മലയാളം" },
	{ code: "pa", name: "Punjabi", native: "ਪੰਜਾਬੀ" },
	{ code: "ur", name: "Urdu", native: "اردو" },
	{ code: "as", name: "Assamese", native: "অসমীয়া" },
	{ code: "sa", name: "Sanskrit", native: "संस्कृतम्" },
	{ code: "ne", name: "Nepali", native: "नेपाली" },
	{ code: "si", name: "Sinhala", native: "සිංහල" },

	// ─── English variants (treated as 'en' by Whisper) ────────────────
	{ code: "en", name: "English", native: "English" },

	// ─── MENA — large ERPNext footprint (Bahrain, UAE, Saudi, Egypt) ──
	{ code: "ar", name: "Arabic", native: "العربية" },
	{ code: "fa", name: "Persian", native: "فارسی" },
	{ code: "he", name: "Hebrew", native: "עברית" },
	{ code: "tr", name: "Turkish", native: "Türkçe" },

	// ─── Southeast Asia ───────────────────────────────────────────────
	{ code: "id", name: "Indonesian", native: "Bahasa Indonesia" },
	{ code: "ms", name: "Malay", native: "Bahasa Melayu" },
	{ code: "th", name: "Thai", native: "ไทย" },
	{ code: "vi", name: "Vietnamese", native: "Tiếng Việt" },
	{ code: "tl", name: "Tagalog", native: "Tagalog" },
	{ code: "my", name: "Burmese", native: "မြန်မာဘာသာ" },
	{ code: "km", name: "Khmer", native: "ខ្មែរ" },
	{ code: "lo", name: "Lao", native: "ລາວ" },

	// ─── East Asia ────────────────────────────────────────────────────
	{ code: "zh", name: "Chinese", native: "中文" },
	{ code: "ja", name: "Japanese", native: "日本語" },
	{ code: "ko", name: "Korean", native: "한국어" },

	// ─── Europe — Western ─────────────────────────────────────────────
	{ code: "es", name: "Spanish", native: "Español" },
	{ code: "pt", name: "Portuguese", native: "Português" },
	{ code: "fr", name: "French", native: "Français" },
	{ code: "de", name: "German", native: "Deutsch" },
	{ code: "it", name: "Italian", native: "Italiano" },
	{ code: "nl", name: "Dutch", native: "Nederlands" },
	{ code: "ca", name: "Catalan", native: "Català" },
	{ code: "eu", name: "Basque", native: "Euskara" },
	{ code: "gl", name: "Galician", native: "Galego" },

	// ─── Europe — Nordic ──────────────────────────────────────────────
	{ code: "sv", name: "Swedish", native: "Svenska" },
	{ code: "da", name: "Danish", native: "Dansk" },
	{ code: "no", name: "Norwegian", native: "Norsk" },
	{ code: "fi", name: "Finnish", native: "Suomi" },
	{ code: "is", name: "Icelandic", native: "Íslenska" },

	// ─── Europe — Central / Eastern ───────────────────────────────────
	{ code: "pl", name: "Polish", native: "Polski" },
	{ code: "cs", name: "Czech", native: "Čeština" },
	{ code: "sk", name: "Slovak", native: "Slovenčina" },
	{ code: "hu", name: "Hungarian", native: "Magyar" },
	{ code: "ro", name: "Romanian", native: "Română" },
	{ code: "bg", name: "Bulgarian", native: "Български" },
	{ code: "el", name: "Greek", native: "Ελληνικά" },
	{ code: "uk", name: "Ukrainian", native: "Українська" },
	{ code: "ru", name: "Russian", native: "Русский" },
	{ code: "sr", name: "Serbian", native: "Српски" },
	{ code: "hr", name: "Croatian", native: "Hrvatski" },
	{ code: "sl", name: "Slovenian", native: "Slovenščina" },
	{ code: "lt", name: "Lithuanian", native: "Lietuvių" },
	{ code: "lv", name: "Latvian", native: "Latviešu" },
	{ code: "et", name: "Estonian", native: "Eesti" },

	// ─── Africa ───────────────────────────────────────────────────────
	{ code: "sw", name: "Swahili", native: "Kiswahili" },
	{ code: "af", name: "Afrikaans", native: "Afrikaans" },
	{ code: "am", name: "Amharic", native: "አማርኛ" },
	{ code: "yo", name: "Yoruba", native: "Yorùbá" },
	{ code: "ha", name: "Hausa", native: "Hausa" },

	// ─── Latin America (Spanish/Portuguese covered above; add indigenous) ─
	// (No additional Whisper entries — Spanish/Portuguese cover the region.)

	// ─── Misc widely used ─────────────────────────────────────────────
	{ code: "az", name: "Azerbaijani", native: "Azərbaycan" },
	{ code: "kk", name: "Kazakh", native: "Қазақ" },
	{ code: "uz", name: "Uzbek", native: "Oʻzbek" },
	{ code: "mn", name: "Mongolian", native: "Монгол" },
];

/**
 * Look up a language by ISO-639-1 code (case-insensitive, region stripped).
 * Returns null if not in the curated list.
 */
export function findLanguage(code) {
	if (!code) return null;
	const norm = String(code).split("-")[0].toLowerCase();
	return WHISPER_LANGUAGES.find((l) => l.code === norm) || null;
}

/**
 * Resolve the locale to use for Whisper from:
 *   1. Explicit user choice (profile locale) — wins if set
 *   2. Browser locale (navigator.language) — fallback
 *   3. "en" — last resort
 */
export function resolveWhisperLanguage(profileLocale) {
	const candidates = [profileLocale, typeof navigator !== "undefined" ? navigator.language : null, "en"];
	for (const c of candidates) {
		if (!c) continue;
		const lang = findLanguage(c);
		if (lang) return lang.code;
	}
	return "en";
}
