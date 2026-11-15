# YJ64 Engineering Core — architecture

## System responsibilities

- Consortium / application: design discussion, project state, permissions, routing and revision history.
- Vision-capable model: interprets user sketches, photographs and markup; returns observations tied to image coordinates.
- Yacht CAD service: owns validated parametric hull geometry and generates editable 2D/3D artifacts.
- Physics service: consumes a versioned geometry/mesh and material/load definitions through bounded solver adapters.
- Commercial agent: evaluates manufacturing and lifecycle cost using traceable engineering inputs.
- Independent oversight: reviews assumptions, evidence and proposed real-world actions.

## Hull geometry contract

The initial design target is a single monohull outer envelope. A hull is represented by an ordered list of longitudinal stations. Each station defines x position, half-beam, keel height, chine height and deck-edge height, all in SI metres. The section profile is currently a simple five-point chine shape. Station ordering and vertical relationships are validated before CAD generation.

The same validated YachtHull object drives all current hull outputs:
- 2D SVG technical sketch: plan, profile and transverse sections;
- editable OpenSCAD polyhedron source;
- FreeCAD macro that creates a loft and exports native FCStd, STEP and STL when deliberately executed;
- optional direct OpenSCAD STL rendering in a bounded subprocess.

The 2D view is a preliminary technical sketch, not a manufacturing drawing. The 3D model is the outer hull envelope only; it does not yet contain frames, stringers, bulkheads, laminate, plate thickness or scantlings.

## Design iteration and image input

Natural-language interpretation is separated from geometry mutation:
1. The language model interprets the user's words and proposes a structured change operation.
2. apply_hull_changes accepts only a small whitelist: set_station, scale_beam, translate_vertical and rename.
3. The updated station data is revalidated.
4. A before/after parameter record is returned.
5. The CAD service regenerates 2D and 3D artifacts from the new parameter set.

Visual collaboration uses the same controlled edit path:
- ingest_reference_image accepts PNG/JPEG, records dimensions, SHA-256 and a local URI;
- ImageAnnotation stores normalized user markup points;
- VisualObservation stores vision-model descriptions, confidence and normalized image regions;
- visual_changes converts only annotations with explicit station/field/value targets into structured edits.

The image module does not itself perform semantic image recognition. A vision-capable model in the consortium must inspect the picture and return observations. Low-confidence or ambiguous observations must be presented to the user for clarification rather than silently changing the hull.

## Dispatcher and pipeline

EngineeringDispatcher requires explicit operation names. CAD backends may return one or many ArtifactReference values; each generated artifact has its own media type, URI and optional SHA-256 digest.

EngineeringPipeline can run:
- CAD-only during early shape exploration;
- CAD plus an explicit physics operation once a suitable hull solver exists.

A branch failure must not suppress the other branch. A completed CAD generation does not imply that a hull is structurally sound.

## Visual and CAD artifact traceability

Each design request has a stable request ID. Generated files use a sanitized version of that ID. Multi-artifact CAD responses return separate artifact references. Reference images retain a SHA-256 digest so later revisions can identify the exact user markup or source image. Structured edits include before/after geometry and the originating operations.

## Physics boundary and next milestone

The existing CalculiX T3D2 adapter is a one-element axial truss check. It is not a hull solver and must not be used to report hull strength.

The next hull-specific physics milestone is:
1. define structural components and material/laminate thickness separately from the outer moulded surface;
2. generate a controlled shell mesh from the CAD geometry;
3. validate mesh topology, normals, element quality and units;
4. define boundary conditions and representative load cases with explicit user review;
5. run a CalculiX shell analysis;
6. check reaction balance, mesh convergence and solver warnings;
7. return contour data and numerical summaries linked to the exact geometry revision.

Hydrostatics, stability, resistance, slamming, fatigue, CFD, appendages, foils and catamaran assembly are later extensions. The first target is deliberately a single hull to keep the geometry and validation loop testable.

## Security and reliability

- Do not execute arbitrary LLM-generated Python.
- Only whitelisted parameter edits may mutate hull geometry.
- Keep artifacts inside a configured project workspace.
- Run OpenSCAD, FreeCAD and FEM tools in isolated workers with time and resource limits.
- Never treat a rendered model as engineering validation.
- Require independent engineering review and physical testing for safety-critical use.
