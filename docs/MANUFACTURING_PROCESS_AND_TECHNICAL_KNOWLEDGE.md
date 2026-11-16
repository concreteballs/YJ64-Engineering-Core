# Manufacturing Processes and Technical Knowledge Architecture

**Status:** planned architecture and research scope. This document does not claim that the process solvers described here are implemented.

## 1. Purpose

YJ64 represents manufacturing as a first-class part of engineering. Material properties depend on composition, product form, manufacturing route, deformation/solidification history, heat treatment, microstructure, direction, defects and service conditions.

The system covers metallic and non-metallic materials. Casting/moulding, forging/forming, heat treatment, additive manufacturing, machining, joining and inspection are separate process families linked to a shared material-state model.

## 2. Process families

### 2.1 Casting and moulding

**Metals and alloys**
- Sand, investment, permanent-mould/gravity, pressure die, low-pressure and centrifugal casting.
- Mould/core and gating design; filling and free-surface flow; vents and feeding; thermal gradients; solidification; shrinkage; porosity; inclusions; hot tearing; residual stress; distortion; machining allowance and inspection.

**Polymers**
- Thermoplastic injection moulding; compression and transfer moulding; resin casting; relevant thermoset and reaction-moulding routes.
- Temperature- and shear-dependent rheology, pressure loss, filling, packing/holding, cooling, crystallization where applicable, curing kinetics for thermosets, shrinkage, sink marks, weld/knit lines, fibre orientation, warpage, residual stress and mould design.
- Polymer process models distinguish thermoplastics from thermosets and do not reuse molten-metal assumptions.

**Other castable materials**
- Glass, ceramics, mineral/cementitious materials, waxes and other project-relevant materials. Select models according to actual chemistry, rheology, phase change or curing behaviour; do not force them into a metal-casting abstraction.

### 2.2 Forging and thermomechanical forming

- Open-die/free forging, closed-die/impression forging, upsetting, drawing-out, cogging, ring rolling and other relevant routes.
- Hot/warm/cold forming where valid for the material.
- Material-specific flow stress, temperature and strain-rate windows, friction, die contact, heat transfer, reheating, cooling, deformation path, grain flow, recrystallization, texture, anisotropy, residual stress, laps, cracks and other defects.
- Maintain distinct validated data for steels, cast/wrought aluminium alloys, copper alloys, nickel alloys, titanium alloys and other families. A generic "metal forging" recipe is not acceptable.

#### Titanium-specific research track
Titanium processing is not treated as ordinary steel forging. The process definition identifies the exact alloy, initial microstructure/product form, section size, phase-region constraints, temperature history, strain rate, deformation sequence, inter-pass time, reheating and cooling conditions.

The proposed route—progressively reducing the workpiece from several sides to a thin intermediate section, then flattening it—is recorded as a research hypothesis. It must be compared against established titanium forging/rolling practice and evaluated for the specified alloy, geometry and process window. It is not a universal instruction or a validated procedure.

The comparison with bulat steel is retained as an idea about staged deformation and structure development, not as a claim that bulat metallurgy and titanium metallurgy are equivalent. The system must identify analogous features and material differences.

### 2.3 Heat treatment and surface engineering

- Annealing, normalizing where applicable, quenching, tempering, solution treatment, ageing/precipitation hardening, stress relief, carburizing, nitriding, induction/flame treatment and other alloy-specific routes.
- Record time-temperature-atmosphere cycles, heating/cooling rates, section size, furnace uniformity, quench medium and severity, phase transformations, precipitation, diffusion, hardness profile, distortion, residual stress, oxidation/decarburization and case depth.
- Link calculated outcomes to composition, prior thermomechanical history and actual test evidence.

### 2.4 Other manufacturing routes
- Metal/polymer/ceramic/composite additive manufacturing; CNC and conventional machining; welding, brazing, soldering, adhesive bonding and mechanical joining; composites lay-up/infusion/cure; forming of sheet, tube and profiles; finishing/coating; metrology and NDT.
- Machine-specific toolpaths and process parameters require exact equipment/controller/tooling/material/setup data and validated postprocessors. A generic geometry export is not a qualified manufacturing program.

## 3. Shared material-state and process record

Every material instance should distinguish:
- specification/grade and verified chemical composition;
- supplier, batch/heat/lot and traceable certificate;
- product form and starting condition;
- manufacturing route and ordered process steps;
- process parameters, equipment identity and calibration where available;
- thermal and deformation history;
- microstructure, grain/texture orientation and defects;
- surface state, coatings and environmental exposure;
- measured properties, test method, specimen orientation, temperature and uncertainty;
- provenance, source revision, licence, extraction method and reviewer;
- model-derived predictions kept separate from measured/certified values.

A process step creates a new versioned material state. It must not overwrite the incoming state or erase chain of custody. Downstream calculations become stale when a relevant upstream state changes.

## 4. Technical books, papers and reference knowledge

YJ64 treats technical literature as traceable engineering knowledge, not as an undifferentiated folder of PDFs.

### 4.1 Source classes
- textbooks and handbooks;
- standards and codes;
- peer-reviewed papers and theses;
- government, university and laboratory reports;
- manufacturer process manuals and datasheets;
- open experimental datasets and benchmark cases;
- historical/archival sources, clearly labelled as such.

### 4.2 Bibliographic leads supplied for initial review
- Shapiro (Шапиро), forging textbooks/technical works — exact author identity, title, edition, publisher and year to be verified.
- Arkhangelsky (Архангельский), forging/forming literature — exact bibliographic record to be verified.
- P. P. Aosov (П. П. Аосов), *О булатах* — preserve the spelling/title as supplied pending catalogue verification.
- Western-language literature on forging, titanium processing, casting, polymer moulding and heat treatment — search across English and other relevant languages, prioritizing primary technical sources and current editions.

These are search leads, not verified citations. Do not invent publication details or assume a particular edition.

### 4.3 Ingestion and linking workflow
1. Create a bibliographic record with verified title, author/editor, edition, year, publisher, language, ISBN/DOI/catalogue identifier, source URL and access date.
2. Record copyright/licence/access status and permitted uses before storing or redistributing content.
3. Ingest only lawfully accessible material: public-domain/open-licensed works, licensed sources, or user-provided copies for permitted private analysis. Do not publish complete copyrighted books or large verbatim extracts.
4. Preserve the original file as an immutable source artifact where storage is permitted; compute a hash and record format, page count and OCR/extraction quality.
5. Extract structured passages, equations, tables, diagram metadata and process descriptions with exact page/section/figure/table references. Preserve original language and units.
6. Add translations only as linked derivatives; never replace source wording or silently convert numerical values.
7. Normalize concepts into a controlled vocabulary: process family, material/alloy, product form, equipment, parameter, defect, property, test method and applicability range.
8. Link each extracted claim to its source location, extraction method, confidence, reviewer and conflicting sources.
9. Separate source statements, YJ64 interpretations, hypotheses, equations implemented in code and experimentally validated results.
10. Turn suitable examples into reproducible benchmark cases only after independent review of inputs, units, boundary conditions and expected outputs.

### 4.4 Knowledge-to-model promotion gates
A book passage does not automatically become a solver equation or production recipe. Promotion requires source and edition verification; competent review; dimensional and physical consistency checks; comparison with authoritative sources; declared applicability; implementation tests and reference benchmarks for executable equations; experimental correlation and uncertainty assessment for physical validation; and versioned review/release.

Contradictions between sources remain visible. The system may report competing models or process windows rather than force false consensus.

## 5. Suggested technical data model

Use linked, versioned entities rather than embedding all knowledge in one document:
- BibliographicSource
- SourceArtifact
- SourcePassage
- TechnicalClaim
- ProcessFamily
- ProcessRoute
- ProcessStep
- MaterialState
- ProcessParameterSet
- DefectObservation
- PropertyMeasurement
- BenchmarkCase
- ModelApplicabilityRecord
- ReviewDecision

Each entity has stable identity, schema version, provenance and explicit relationships. Exact implementation belongs in the common project/artifact architecture and discipline packs; this document defines target semantics, not a commitment to these exact class names.

## 6. Validation and safety boundaries

- A literature-derived parameter range is not automatically safe or suitable for a particular workpiece.
- Do not generate production-ready furnace/press/forge/moulding settings without exact material, equipment, geometry, process and validated procedures.
- Titanium and other reactive/high-temperature alloys require process-specific controls, atmosphere/contamination considerations and qualified equipment procedures.
- Distinguish educational explanation, preliminary screening, numerical simulation, qualified process specification and certified production.
- Preserve failed trials and negative evidence with their conditions; do not curate only successful examples.

## 7. Initial implementation sequence

1. Extend material records to carry composition, product form, process history, heat treatment and evidence provenance.
2. Define process-family and process-step schemas without hard-coding every discipline into the kernel.
3. Build a literature registry and page/section-level source citation model.
4. Create curated reference datasets for selected steel, aluminium, titanium and polymer cases.
5. Select one small casting, one polymer moulding, one forging and one heat-treatment benchmark from openly usable/verified sources.
6. Implement or adapt specialist solvers only after benchmark definitions and candidate-tool review.
7. Add experimental evidence intake and compare predicted versus measured microstructure/property/defect outcomes.

## 8. Explicit current status

This is planned scope. The repository currently has material evidence foundations and limited material screening, but no general metal-casting, polymer-moulding, forging, titanium-forging or heat-treatment simulation engines, nor a complete literature ingestion/retrieval system.
