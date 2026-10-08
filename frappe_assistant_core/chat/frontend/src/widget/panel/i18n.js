const fill = (s, args) => (args ? s.replace(/\{(\d+)\}/g, (_m, i) => args[i]) : s);

/** Desk's translator when present; the English source string otherwise. */
export const t = (s, args) => (window.__ ? window.__(s, args) : fill(s, args));
