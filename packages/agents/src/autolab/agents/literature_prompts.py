from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autolab.agents.literature_models import (
    AssumptionStageResult,
    CitationChainStageResult,
    ContradictionStageResult,
    FieldSynthesis,
    GapStageResult,
    IntakeResult,
    KnowledgeMap,
    MethodologyAudit,
    SoWhatSummary,
)
from pydantic import TypeAdapter

LITERATURE_RESEARCH_SYSTEM_PROMPT = """
You are the Literature Research Engine for a technical research stack.
Build a field-level model of the literature rather than paper-by-paper summaries.
Prefer rigor over hype. Distinguish direct evidence from inference. State uncertainty,
evidence quality, and where apparent consensus is weak or absent. Avoid fake synthesis.
Work well for physics, machine learning, and adjacent technical fields.

Always perform these stages in order:
1. Intake Protocol
2. Contradiction Finder
3. Citation Chain
4. Gap Scanner
5. Methodology Audit
6. Master Synthesis
7. Assumption Killer
8. Knowledge Map Builder
9. So What Test

Return structured JSON that matches the requested stage schema exactly.
""".strip()


@dataclass(frozen=True, slots=True)
class StagePromptTemplate:
    purpose: str
    template: str
    output_schema: dict[str, Any]


_STAGE_OUTPUT_MODELS = {
    "intake_protocol": IntakeResult,
    "contradiction_finder": ContradictionStageResult,
    "citation_chain": CitationChainStageResult,
    "gap_scanner": GapStageResult,
    "methodology_audit": MethodologyAudit,
    "master_synthesis": FieldSynthesis,
    "assumption_killer": AssumptionStageResult,
    "knowledge_map_builder": KnowledgeMap,
    "so_what_test": SoWhatSummary,
}


def _schema(stage_name: str) -> dict[str, Any]:
    return TypeAdapter(_STAGE_OUTPUT_MODELS[stage_name]).json_schema()


LITERATURE_STAGE_PROMPTS = {
    "intake_protocol": StagePromptTemplate(
        purpose=(
            "Normalize the paper set, list each paper's core claim, "
            "cluster the set, and flag weak inputs."
        ),
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Paper metadata: {{paper_metadata}}

Perform Intake Protocol.
- List every paper with author, year, and one-sentence core claim.
- Cluster papers by shared assumptions, methods, and themes.
- Flag duplicates, off-topic papers, weak metadata, and missing context.
- Distinguish what is explicit in the papers from what you infer.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("intake_protocol"),
    ),
    "contradiction_finder": StagePromptTemplate(
        purpose="Surface direct disagreements and explain why they disagree.",
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Extracted claims: {{extracted_claims}}

Perform Contradiction Finder.
- Identify direct disagreements between papers.
- For each contradiction, state both positions, cite the relevant papers,
  and classify the source as data, methods, definitions, assumptions,
  or interpretation.
- Avoid inventing contradictions when evidence is weak.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("contradiction_finder"),
    ),
    "citation_chain": StagePromptTemplate(
        purpose="Trace central concepts through the literature set.",
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Citation graph: {{citation_graph}}
Extracted claims: {{extracted_claims}}

Perform Citation Chain.
- Identify the most central concepts.
- For each concept, trace who introduced it, who challenged it,
  who refined it, and the current consensus if any.
- Be explicit when the provided evidence is too sparse for a strong chain.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("citation_chain"),
    ),
    "gap_scanner": StagePromptTemplate(
        purpose="Find the most important unanswered questions and next evidence needed.",
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Extracted claims: {{extracted_claims}}
Contradictions: {{contradictions}}

Perform Gap Scanner.
- Identify important unanswered questions.
- Explain why each gap still exists.
- Name which paper came closest.
- Propose the experiment, simulation, dataset, or analysis that would close the gap.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("gap_scanner"),
    ),
    "methodology_audit": StagePromptTemplate(
        purpose=(
            "Compare methods, dominant approaches, likely biases, and method-sensitive conclusions."
        ),
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Methodology map: {{methodology_map}}

Perform Methodology Audit.
- Group methods into experiments, simulations, theory, surveys, meta-analyses, and case studies.
- Identify dominant methods, underused methods, likely biases,
  and conclusions that depend heavily on methodology.
- Separate direct methodological evidence from your inference.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("methodology_audit"),
    ),
    "master_synthesis": StagePromptTemplate(
        purpose="Produce the field-level synthesis, not a paper-by-paper dump.",
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Extracted claims: {{extracted_claims}}
Research gaps: {{research_gaps}}
Contradictions: {{contradictions}}

Perform Master Synthesis.
- State what the field collectively believes.
- State what remains contested.
- State what assumptions most work shares.
- State what seems most promising next.
- Avoid fake consensus and note evidence quality.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("master_synthesis"),
    ),
    "assumption_killer": StagePromptTemplate(
        purpose="Surface hidden assumptions and describe what breaks if they fail.",
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Extracted claims: {{extracted_claims}}
Methodology map: {{methodology_map}}

Perform Assumption Killer.
- List assumptions that many papers rely on but rarely test.
- Explain what breaks if each assumption is false.
- Prefer assumptions grounded in the provided evidence.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("assumption_killer"),
    ),
    "knowledge_map_builder": StagePromptTemplate(
        purpose="Condense the field into a compact knowledge map.",
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Extracted claims: {{extracted_claims}}
Contradictions: {{contradictions}}
Research gaps: {{research_gaps}}

Perform Knowledge Map Builder.
- Output one central claim.
- Output 3 to 5 supporting pillars.
- Output 2 to 3 contested zones.
- Output 1 to 2 frontier questions.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("knowledge_map_builder"),
    ),
    "so_what_test": StagePromptTemplate(
        purpose="End with what is proven, unknown, and why it matters.",
        template="""
Topic: {{topic}}
Paper set: {{paper_set}}
Extracted claims: {{extracted_claims}}
Research gaps: {{research_gaps}}

Perform So What Test.
- One sentence on what the field has proven.
- One sentence on what it still does not know.
- One sentence on why it matters in practice.

Return JSON only using this schema:
{{output_schema}}
""".strip(),
        output_schema=_schema("so_what_test"),
    ),
}


def get_literature_stage_prompt(stage_name: str) -> StagePromptTemplate:
    return LITERATURE_STAGE_PROMPTS[stage_name]


def get_literature_stage_schema(stage_name: str) -> dict[str, Any]:
    return LITERATURE_STAGE_PROMPTS[stage_name].output_schema
