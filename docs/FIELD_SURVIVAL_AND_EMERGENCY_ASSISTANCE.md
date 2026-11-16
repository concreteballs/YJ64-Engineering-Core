# Field Survival and Emergency Assistance Modules

## Purpose and architecture

Define optional operational modules that help a person solve immediate field/emergency tasks using available knowledge, tools, materials and environmental context. These modules are separate from the engineering physics kernel and are assembled with shared services only when required. They must be individually installable, versioned and usable offline when their data bundles are present.

## Operational modules

### First aid and emergency medical information

Provide conservative first-aid guidance, scene safety, emergency triage support, injury/illness information, red-flag recognition, escalation and locally configured emergency-contact information. Distinguish observed symptoms from possible causes and from diagnosis. Ask for essential facts only when needed. Prioritize emergency services and established first-aid guidance. Medical content must be reviewed by qualified professionals, carry source/revision dates and local jurisdiction information, and must not claim to replace diagnosis or treatment by a clinician.

### Chemistry, water and fire

Provide practical chemical and environmental knowledge with hazard identification, concentration/context checks, incompatibility warnings and safe alternatives. Water guidance must distinguish biological hazards from chemical, salinity, fuel and heavy-metal contamination; boiling or ordinary disinfection does not remove dissolved chemical contaminants. Fire guidance should prioritize low-risk established methods and fire prevention, ventilation and burn/forest-fire risks. Never improvise hazardous chemical mixtures as generic survival recipes.

### Field materials, minerals and geography

Support identification as a confidence-ranked hypothesis from descriptions, measurements and images; distinguish visual guess from field-test evidence. Include local geology/minerals, terrain, climate, ecology and resource constraints only where sourced and geographically applicable. Avoid claiming that a mineral or plant is safe/useful based on appearance alone.

### Woodworking, shelter, energy and repair

Offer material selection, hand-tool methods, simple joints, shelter/weather protection, insulation, heat management, energy budgeting and repair concepts. Instructions must account for tool availability, skill level, structural loads, moisture, wind and fire risk. Generated procedures remain advisory until checked against the actual materials and conditions.

### Emergency signalling and communications

Prioritize high-visibility/low-complexity methods: internationally recognized distress signals, mirror/reflective signalling, lights, sound, ground markings and approved emergency beacons/radios when available. If radio equipment exists, assist with safe documented operation and distress-message preparation. Do not assume a homemade transmitter is practical, legal or reliable; assess spectrum rules, power, antenna, propagation, available components and risk before suggesting any construction. Prefer existing certified equipment and known distress channels.

### Emergency and celestial navigation

Link to POSITION_TIME_AND_NAVIGATION_INTEGRATION.md. Provide offline position/time estimation, manual observation logging, improvised instrument instructions, celestial observations and uncertainty-aware navigation as a separate optional workflow. Never imply that a phone's magnetometer, improvised sextant or dead reckoning yields survey-grade accuracy.

## Adaptive field-task interface

A user may describe an objective and inventory of available tools/materials. The module should:
1. clarify the immediate objective and time/urgency;
2. record available tools, materials, quantities, condition and skill level;
3. establish location/environment and connectivity where known;
4. identify hazards and hard constraints;
5. generate multiple feasible options from reviewed sources and discipline models;
6. compare effectiveness, time, resource cost, failure modes and risks;
7. provide a stepwise plan with checkpoints and stop conditions;
8. identify what cannot be established and what outside assistance is needed.

The system must not optimize only for technical feasibility; human safety, legal constraints, reversibility and simplicity matter. For life-threatening situations, emergency response and immediate risk reduction take precedence over elaborate construction.

## Offline requirements

Preloaded bundles may include first-aid references, chemistry/water guidance, local geography, maps, navigation tables, language packs, materials references and practical manuals. Every bundle records source, licence, region, language, version, publication/review date, checksum and known omissions. Offline responses disclose stale or missing information. Medical and hazardous-material content must be updated and reviewed under a controlled release process.

## Safety and quality gates

- Medical content requires qualified review, local emergency adaptation and clear red flags.
- Chemical instructions require hazard review, compatibility checks and contaminant-specific limits.
- Identification from images/text is probabilistic and must state uncertainty.
- Procedures identify prerequisites, PPE, stop conditions, disposal and escalation where relevant.
- The system cannot present generated content as a certified medical diagnosis, chemical procedure or rescue instruction.

## Status

Planned. No medical, field-survival, chemistry/water, mineral-identification or emergency task workflow is claimed as implemented.
