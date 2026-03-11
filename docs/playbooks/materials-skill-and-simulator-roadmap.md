# Materials Skill And Simulator Roadmap

This note turns the current product direction into a concrete build sequence.

The objective is to evolve `physics_researcher` from a simulator-capable monorepo into a materials research workbench with:

- a curated materials skill profile
- a visible operator-facing interface
- benchmark-grade simulator lanes
- measurement-aware feedback loops

## Strategic outcome

The near-term target is:

"Build a materials skill profile plus a materials workbench UI, then add three benchmark-grade simulator lanes:

- `xTB -> CP2K`
- `LAMMPS -> Elmer/MOOSE`
- `simulation -> XRD/measurement`"

## Workstream 1: Materials skill profile

The project should add a curated skill layer for materials science rather than importing large external skill libraries wholesale.

### Principle

Every skill should be one of:

- native typed execution tool
- imported typed execution tool
- planner-only reasoning aid

Raw markdown skills should not go directly into the execution agent unless they are normalized into a typed contract.

### Initial skill domains

#### Materials data

- crystal structure retrieval
- materials database lookup
- CIF and POSCAR normalization
- phase and composition metadata extraction

Likely integrations:

- Materials Project
- OQMD
- NOMAD

#### Electronic structure

- structure relaxation preparation
- k-point and cutoff recommendation
- DFT job triage
- result summarization and transfer mapping

Likely integrations:

- ASE
- xTB
- CP2K
- Quantum ESPRESSO

#### Atomistic and mesoscale

- force-field bootstrapping
- MD campaign setup
- effective-property extraction
- continuum handoff preparation

Likely integrations:

- LAMMPS
- OpenMM where appropriate
- Elmer
- MOOSE or FiPy

#### Characterization and measurement

- XRD peak extraction
- pattern matching
- experiment-to-simulation comparison
- measurement ingestion and QA

Likely integrations:

- GSAS-II
- pyFAI
- HyperSpy where relevant

#### Scientific analysis and reporting

- uncertainty summaries
- benchmark report generation
- figure generation
- literature and citation support

Use existing strengths where possible:

- statistics
- scikit-learn
- visualization
- literature research

### Skill import policy for external libraries

If external skill libraries such as LabClaw are used later:

1. Import only domains that map to this project's scope.
2. Normalize them into typed metadata.
3. Mark unsupported tool assumptions explicitly.
4. Separate execution-safe skills from planner-only skills.

## Workstream 2: Materials workbench UI

The UI work should follow the architecture in `docs/architecture/materials-workbench-ui.md`.

### First UI milestone

Ship a read-only workbench:

- campaign list
- run details
- artifact visibility
- benchmark report browser
- skill catalog

### Second UI milestone

Ship structured editing:

- campaign creation
- workflow graph editing
- simulator-stage templates
- comparison views

### Third UI milestone

Ship operator loop features:

- measurement inbox
- approval checkpoints
- benchmark leaderboards
- review workflows

## Workstream 3: Benchmark-grade simulator lanes

The next simulator work should prioritize materials-science credibility over breadth.

### Lane A: xTB -> CP2K

Goal:

- cheap pre-screening followed by stronger condensed-matter calculations

Why this lane matters:

- it gives the repo a realistic path from broad screening to higher-fidelity evaluation
- it is more useful for materials workflows than trying to jump directly to a heavy DFT-only path everywhere

Required capabilities:

- ASE-based structure model normalization
- xTB pre-relaxation or cheap screening stage
- CP2K refinement stage
- typed transfer mapping from xTB outputs into CP2K setup
- benchmark task definitions and artifact expectations

Initial benchmark ideas:

- polymorph triage
- adsorption-site ranking
- defect configuration screening

### Lane B: LAMMPS -> Elmer or MOOSE

Goal:

- connect atomistic simulation outputs to continuum or process models

Why this lane matters:

- it gives the project a true multiscale materials story
- it builds directly on adapters the repo already has or is close to having

Required capabilities:

- extraction of effective properties from atomistic runs
- explicit mapping contracts into continuum parameters
- verification of stage-to-stage transfer assumptions
- benchmark tasks with physically interpretable metrics

Initial benchmark ideas:

- thermal transport handoff
- thermo-mechanical property transfer
- process-window screening under constrained material parameters

### Lane C: simulation -> XRD or measurement

Goal:

- connect simulated candidates to experimental evidence

Why this lane matters:

- it moves the repo toward a real lab operating system rather than a simulator manager
- it enables ranking candidates by agreement with measurement instead of simulation score alone

Required capabilities:

- typed measurement stage for XRD ingestion
- artifact schemas for raw spectra, metadata, and parsed peaks
- comparison logic between simulated and observed patterns
- operator confirmation for ambiguous parses

Initial benchmark ideas:

- phase identification agreement
- peak-position error
- pattern similarity ranking

## Suggested implementation order

### Phase 1: foundation

1. Add a machine-readable skill metadata model.
2. Add registry export endpoints for the future Skill Catalog.
3. Add a benchmark report index model.
4. Add artifact-listing endpoints by run and stage.

### Phase 2: first visible product surface

1. Build read-only Campaigns and Runs pages.
2. Build the first Skill Catalog page.
3. Build the first Benchmark Hub page.
4. Add a workflow graph viewer to existing campaign details.

### Phase 3: first materials lane

1. Introduce ASE as the unifying structure layer.
2. Add an `xtb` adapter.
3. Add a `cp2k` adapter.
4. Create one benchmark manifest for `xtb -> cp2k`.

### Phase 4: multiscale lane

1. Strengthen the `lammps` transfer outputs.
2. Add `moose` or `fipy` based continuum support.
3. Create one benchmark manifest for `lammps -> continuum`.

### Phase 5: measurement lane

1. Add XRD ingestion and parsing.
2. Add a measurement inbox interface.
3. Create one benchmark manifest for simulation-to-measurement matching.

## Success criteria

The product direction becomes real when the repo can demonstrate:

- a visible materials workbench interface
- a searchable, typed materials skill catalog
- at least one reproducible benchmark in each of the three target lanes
- run-level provenance that an operator can inspect without reading raw files manually
- a clear story for how simulated candidates are compared against measurement evidence

## What not to do now

- do not import hundreds of external skills without a contract layer
- do not market XR or robotics before corresponding adapters exist
- do not add many simulators without benchmark tasks that justify them
- do not let the UI degrade into a generic CRUD admin panel
