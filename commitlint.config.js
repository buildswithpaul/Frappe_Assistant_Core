/**
 * commitlint configuration.
 *
 * Extends @commitlint/config-conventional (angular preset) — the same ruleset
 * referenced by .github/workflows/commitlint.yml and required by
 * semantic-release for version-bump detection.
 *
 * The `ignores` list holds specific historical commits that predate strict
 * rule enforcement and cannot be rewritten (they're referenced by merged PRs
 * and are already on main/develop). Each predicate matches the squashed
 * commit's subject by its PR number suffix, which is unique and stable.
 * Every entry must cite the PR it belongs to.
 *
 * Do not add new entries lightly — future PRs get linted at submission time,
 * so only squash-merge accidents from the CI-gap era belong here.
 */
module.exports = {
    extends: ['@commitlint/config-conventional'],
    ignores: [
        // PR #145 — feat: Skills subsystem — FAC Skill DocType, admin tabs,
        // external app registration. Squash-merged with "Skills" in
        // sentence-case after the colon, violating subject-case.
        (message) => message.includes('(#145)') && message.includes('Skills subsystem'),

        // PR #143 — Fix audit log false-success and enrich captured fields.
        // Squash-merged without a conventional-commit type prefix ("Fix"
        // instead of "fix:"), violating both type-empty and subject-case.
        (message) => message.includes('(#143)') && message.includes('Fix audit log false-success'),
    ],
};
