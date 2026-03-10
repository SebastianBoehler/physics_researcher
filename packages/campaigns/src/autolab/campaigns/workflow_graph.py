from __future__ import annotations

from autolab.core.models import Campaign, Candidate, SimulationStage, SimulationWorkflow
from autolab.simulators import SimulatorRegistry


def resolve_campaign_workflow(
    campaign: Campaign, candidate: Candidate, simulator_registry: SimulatorRegistry
) -> SimulationWorkflow:
    if campaign.workflow is not None:
        return campaign.workflow
    backend = simulator_registry.get(campaign.simulator)
    return backend.default_workflow(candidate)


def stage_order(workflow: SimulationWorkflow) -> list[SimulationStage]:
    return workflow.ordered_stages()
