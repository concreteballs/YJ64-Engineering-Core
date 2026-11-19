# Biological Engineering Module

## Status and boundary

This document specifies an independent, optional Biological Engineering module. It is not a subpackage of YJ64 Engineering Core, Molecular & Genetic Engineering or Robotics. It connects through versioned universal task, extension, evidence, material, interface and hazard contracts. Its internal models and release cadence remain independently managed.

The module owns biological materials and organism/system-level biological engineering. It does not own molecular/genetic design, general chemistry, robot architecture or system-level approval. It may consume reviewed outputs from Molecular & Genetic Engineering and publish candidate material/system properties to other modules.

## Scope

1. Biological and bio-derived materials, biocomposites and biofabricated structures.
2. Biohybrid actuator concepts and living/tissue-based actuation as research candidates.
3. Microbial and fungal interactions with material surfaces, including colonisation, degradation and biofouling.
4. Controlled surface-protection and surface-maintenance concepts.
5. Contamination monitoring, sensing, inspection and evidence management.
6. Validated cleaning, disinfection and decontamination compatibility assessment.
7. Containment, exposure pathways, persistence, shedding, waste and end-of-life.
8. Environmental and human-interface impact assessment.

## Research and evaluation

Biohybrid actuator hypotheses—including collective contraction under electrical or magnetic stimulation—must be treated as unproven until supported by reproducible evidence. Start with literature assessment, computational models and non-living baselines. Evaluate force, stroke, speed, efficiency, controllability, repeatability, fatigue, lifetime, environmental stability, energy/nutrient requirements, metabolites/by-products, waste, maintenance, containment and failure modes.

Compare against non-biological alternatives such as elastomers, electroactive polymers, shape-memory materials, pneumatic/hydraulic actuators and conventional mechanisms. Biological approaches are not presumed simpler, safer, cheaper or more robust.

## Robot hygiene and fomite risk

A robot may mechanically carry contamination even when it cannot itself become clinically ill. Assess touch surfaces, seams, porous layers, internal cavities, air/liquid paths, tools, connectors, filters, charging/service interfaces, storage and transport between zones. Require cleanability, inspectability, service traceability and validated decontamination appropriate to the intended environment.

Biological surface maintenance and bacteriophage concepts are limited research options, not universal disinfectants. Phages are host/bacterium-specific and are not general antiviral agents. They do not replace validated cleaning, disinfection or sterilisation. No open self-propagating biological layer is assumed acceptable on robots operating near people.

## Biosafety boundaries

Prefer well-characterized non-pathogenic research systems and non-living alternatives where appropriate. Any biological work requires qualified biosafety review, appropriate containment, exposure assessment, monitoring, validated inactivation and waste handling. Do not design for uncontrolled spread, environmental release, increased pathogenicity, host-range expansion, immune evasion or resistance to containment. This module specification does not provide organism construction, genetic modification, culture, propagation or pathogen-handling protocols.

## Module output contract

Every candidate output includes:
- module ID/version and task/schema version;
- intended use and applicability envelope;
- source/provenance and evidence maturity;
- measured, inferred, simulated and unknown properties clearly separated;
- assumptions, uncertainty, limitations and reproducibility references;
- material/system interfaces and downstream dependencies;
- hazards, exposure routes, containment requirements and lifecycle effects;
- required independent reviews and unresolved questions.

The module may certify only its own declared domain-level checks. It cannot declare a complete robot, product or deployment safe. Cross-module review is mandatory under the shared protocol.

## Evidence gates

Label outputs as concept/hypothesis, literature-supported plausibility, computational result, independently benchmarked model, controlled experimental evidence, replicated evidence or application-qualified evidence. No simulation or model consensus is treated as experimental validation.
