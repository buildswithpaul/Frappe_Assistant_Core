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
// PR promantia-ai#13 (feature/data-migration into develop): 31 commit headers written
// before the branch was linted. 27 other branches share these commits, so they can't be
// rewritten. Only these exact first lines are ignored; every other commit is linted.
const DATA_MIGRATION_HEADERS = new Set([
    "feat(tools): ERPNext validates the opening stock as a draft, rolled back (#33996)",
    "fix(tools): opening stock review fixes: remember what is in, one bad row fails alone, report every chunk (#33996)",
    "test(import): assert each opening invoice cause's explanation and fixes; refuse mapping a disabled party to nobody (#33997)",
    "fix(import): opening invoice report says when an import stopped, caps honestly, guards the queue (#33997)",
    "feat(import): load and validate import presets from FAC and the assistant_import_presets hook (#34000)",
    "feat(import): Tally Prime and QuickBooks Online import presets (#34000)",
    "feat(import): QuickBooks Desktop, Zoho Books, Busy and Marg import presets (#34000)",
    "fix(import): format Task 6 tests, wider account type maps, Busy \"as on\" title, group flag tests (#34000)",
    "docs(import): Tally XML in the apply_import_preset skill (#34001)",
    "test(import): cover reader fallbacks, DTD, per-part metadata, routing and refusals for Tally XML (#34001)",
    "chore(merge): merge feature/34004-migrate-data-skill into feature/data-migration-33996-34000 (#34004)",
    "docs(import): Stock rows are left out of the opening entry only with perpetual inventory (#33998)",
    "test(import): Desk sees FAC's import job running on v15 and v16 (#34397)",
    "fix(import): FAC's own argument errors aren't fenced as file content (#34003)",
    "fix(import): plan questions fence only what the files say, and the approval comes back as given (#34438)",
    "fix(import): the approval's decision lines and the order, waiting and blocked messages stay fenced (#34438)",
    "fix(import): openings take the company's own Temporary account and see an earlier opening entry (#34433)",
    "fix(import): the required check reads the file's cell; release checks the role itself (#34537, #34538)",
    "feat(import): the sign-off states its scope, and a plan is shown before its questions (#34549, #34546)",
    "fix(import): a tool's own error and message read as FAC's, with what they quote as data (#34550, #34438)",
    "fix(import): a migration plan's questions cost no approvals, and a wrong answer key costs nothing (#34547)",
    "fix(import): FAC's note on a file reaches the model as its own text (browser test BT-8)",
    "fix(tests): import tests delete only their own files; retention tests purge only their sessions (#34606)",
    "feat(import): System Managers see every import session and release a stuck one (#34542)",
    "fix(chat): FAC Chat's socket finds the socketio port when bench start serves the site",
    "feat(import): FAC Import Key Map remembers which old ID became which record (#34244)",
    "fix(import): Tally stock groups are imported as Item Groups under their parents (#34001)",
    "feat(import): FACO posts the result when a background check, import or plan ends (#34416)",
    "fix(import): an accountant can translate an opening file's old party IDs without Import permission (#33997)",
    "fix(import): \"Apply all suggested answers\" asks for a fill's value instead of leaving the rows out (#34351)",
    "fix(import): Tally parties get a group, and each part's card names its own file",
]);

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

        // PR promantia-ai#13: the 31 headers in DATA_MIGRATION_HEADERS above.
        (message) => DATA_MIGRATION_HEADERS.has(message.split('\n')[0].trim()),
    ],
};
