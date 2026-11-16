# Multilingual Engineering Workspace

## Purpose

YJ64 must let engineers work in their preferred language and read technical documentation without leaving the engineering environment. The platform supports multilingual UI, technical-document translation and independent unit-system conversion. These are cross-cutting platform services shared by every discipline and application pack.

## Core design rules

1. **Engineering data is language-neutral.** Stable identifiers, schema keys, enum values, solver interfaces, material IDs, component IDs and machine-readable quantities never depend on translated labels.
2. **Localization is a presentation layer.** UI labels, help, reports and document views resolve through locale resources. The original source artifact remains preserved and addressable.
3. **Translation and unit conversion are independent.** A user may translate text while retaining original units, convert units without translating text, or do both in one view.
4. **No silent engineering edits.** Translation must not change numeric values, signs, tolerances, equations, variable names, identifiers, part numbers, standard designations, citations, warnings or safety statements. Any intentional unit conversion is an explicit, separately recorded transformation.
5. **Traceability is mandatory.** Every translated or converted view records source artifact/revision, source and target locales, glossary/version, translation engine/model/version, conversion profile, timestamp, warnings and review state.
6. **Uncertainty is visible.** Ambiguous terminology, unreadable source text, unsupported notation and low-confidence passages are flagged for human review, not guessed.

## Language and locale model

- Store language tags using BCP 47 conventions (for example, en, en-GB, es, ru); distinguish language from regional formatting preferences.
- Support per-user UI locale, per-project working language, per-document source language and per-view target language.
- Keep locale-specific formatting separate from engineering values: decimal separators, grouping separators, date/time formats and translated unit names/symbols must not alter canonical data.
- Use stable message keys and parameterized plural-aware resources; never use translated text as a programmatic key.
- Allow mixed-language projects and documents. Preserve original-language quotations and terms when useful, with glossary-backed translated equivalents.
- Plan for right-to-left layout and Unicode-safe search/rendering, even if the first UI languages are left-to-right.

## Technical-document translation pipeline

The first supported document types should be PDF (including scanned PDFs), DOCX, Markdown and plain text; additional formats can be added through import/export adapters.

1. Import the source as an immutable artifact; compute a content hash and retain original bytes/metadata where licensing permits.
2. Extract text, tables, headings, captions, footnotes and structural relationships. For scanned documents, use OCR and preserve page/region references.
3. Detect or confirm source language; let the engineer select target language and translation mode.
4. Segment content while preserving document structure and links between translated segments and source page/paragraph/table cells.
5. Protect technical tokens before translation: equations, code, identifiers, part numbers, units, standards, formula variables, references, tolerances and explicitly protected phrases.
6. Apply project/domain glossaries and termbase rules. Terms may have preferred translations, forbidden variants, definitions and discipline scope.
7. Translate prose and captions with a pluggable translation provider. Providers are replaceable; no single LLM or cloud service is mandatory. A local/offline provider may be added where feasible.
8. Run structural and semantic integrity checks: missing/duplicated segments, changed protected tokens, number/sign mismatch, table alignment, broken references, unit mismatch and suspiciously altered warnings.
9. Render a side-by-side or overlay view with source/target navigation, terminology highlights and reviewer corrections.
10. Export a translated derivative while retaining a link to the immutable source and a translation provenance manifest.

### Translation modes

- **Read-only assist:** translated view for comprehension; original remains authoritative.
- **Reviewed translation:** human-approved terminology and segments, suitable for internal project use.
- **Controlled publication:** export for external/customer/regulatory use only after required human/qualified review. Machine translation alone is not a certified translation and must not be represented as one.

For safety-critical, contractual, regulatory or certification documents, display a persistent status indicating whether the translation is machine-generated, human-reviewed or formally certified by an appropriately qualified party. Preserve the source-language text for audit.

## Engineering terminology and glossary service

A project or discipline glossary entry should support:
- stable concept ID;
- source term and language;
- preferred target terms by locale;
- definition and context;
- discipline/domain scope;
- allowed synonyms and forbidden/ambiguous translations;
- grammatical metadata where needed;
- source/reference, owner, revision and approval state.

Glossaries can be shared across projects, but project-specific overrides must be explicit and versioned. Corrections approved by engineers become reusable terminology evidence; they do not silently rewrite prior translated artifacts.

## Units, quantities and display profiles

- Continue using typed Quantity values and dimension-checked conversions in the shared physics kernel.
- Store canonical numeric values independently of locale and display preferences. SI is the initial canonical interchange convention; preserve source value/unit and provenance when importing external documents.
- Add named unit-system/display profiles (for example SI, metric engineering, US customary, marine-specific or user-defined) and per-discipline/per-field overrides.
- Support one-click conversion of a value, table, selected document, report or project view where dimensions are known. Offer reversible display conversion and explicit converted-copy/export modes.
- Support affine conversions such as °C/°F/K correctly; reject incompatible dimensions and ambiguous symbols. Distinguish absolute temperature from temperature intervals in a later typed-quantity refinement.
- Preserve significant figures, tolerances, uncertainty and range semantics. Do not imply extra precision after conversion or round away engineering tolerances.
- Treat unit symbols as invariant technical tokens by default; localize explanatory names separately. Locale decimal formatting is a rendering choice, not a change to stored values.
- Record source units, target units, conversion rule/registry version and rounding policy in exported artifacts.

The current kernel already has a basic Quantity, UnitDefinition, UnitRegistry and explicit named-unit conversion. It does not yet provide a complete unit catalogue, unit-system profiles, arbitrary compound-unit parsing, locale-aware rendering or document-wide conversion.

## User experience

- A global language selector for the interface, plus independent project/document language controls.
- A document viewer with original/translation side-by-side, synchronized page/paragraph navigation and glossary lookup.
- A visible unit-profile selector and per-value override; show original and converted values together on demand.
- A clear distinction between source document, translated view and converted derivative.
- Review queues for ambiguous terms, OCR failures, numeric discrepancies and protected-token mismatches.
- Search across original and translated text while returning the exact source location.

## Privacy, security and licensing

Technical documents may contain confidential designs or customer data. Before using an external translation provider, disclose what content leaves the device, the provider, retention/training terms where known, and the applicable project policy. Support provider selection, redaction and local processing where feasible. Do not upload documents to a provider without the configured permission. Respect copyright, export controls, document licences and provider terms; retain provenance for imported terminology and datasets.

## Implementation stages

1. **Foundation:** locale metadata, stable message keys, language-neutral schemas, canonical quantity storage and unit display profiles.
2. **Unit UX/API:** conversion service and tests for dimensions, affine temperatures, significant figures, tolerances, locale formatting and reversible display.
3. **Document intake/view:** PDF/DOCX/Markdown/text extraction, immutable source artifacts, source-region mapping and side-by-side viewer contracts.
4. **Translation service:** provider-neutral interface, terminology/glossary service, protected-token pipeline and translation provenance.
5. **Integrity/review:** number/formula/token checks, OCR confidence, reviewer workflow and export of translated derivatives.
6. **Advanced localization:** RTL, offline providers, additional formats, multilingual search and discipline-specific glossary packs.

## Acceptance criteria

- Switching UI language does not change project IDs, solver inputs, numerical values or serialized canonical data.
- A technical document can be translated in-app while retaining a navigable link to every source segment.
- Protected identifiers, equations, standards, part numbers and numeric values are preserved or explicitly flagged; no silent mutation is accepted.
- A user can translate text without changing units, and change units without translating text.
- Unit conversion rejects incompatible dimensions and correctly handles supported affine scales; tolerances and significant figures remain meaningful.
- Every generated translation/conversion derivative records complete provenance and review status.
- External translation is blocked until the applicable data-sharing permission/policy is satisfied.

## Current status

Planned. Existing quantity primitives provide a starting point for unit conversion. Multilingual UI, technical-document ingestion/translation, glossary management, locale-aware rendering, unit profiles and review workflows are not yet implemented.
