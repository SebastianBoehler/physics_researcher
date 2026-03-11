from enum import StrEnum


class CampaignMode(StrEnum):
    MATERIALS_DISCOVERY = "materials_discovery"
    PROCESS_OPTIMIZATION = "process_optimization"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ObjectiveDirection(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ConstraintOperator(StrEnum):
    LESS_THAN = "lt"
    LESS_THAN_EQUAL = "lte"
    GREATER_THAN = "gt"
    GREATER_THAN_EQUAL = "gte"


class ParameterKind(StrEnum):
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    CATEGORICAL = "categorical"


class RunStatus(StrEnum):
    PENDING = "pending"
    PREPARED = "prepared"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class FailureClass(StrEnum):
    NONE = "none"
    TRANSIENT = "transient"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    ENGINE = "engine"
    PARSE = "parse"
    UNKNOWN = "unknown"


class SimulatorKind(StrEnum):
    LAMMPS = "lammps"
    MEEP = "meep"
    QUANTUM_ESPRESSO = "quantum_espresso"
    OPENMM = "openmm"
    ELMER = "elmer"
    DEVSIM = "devsim"
    MANUAL_PROTOCOL = "manual_protocol"
    CSV_MEASUREMENT = "csv_measurement"


class ArtifactType(StrEnum):
    CONFIG = "config"
    INPUT = "input"
    OUTPUT = "output"
    LOG = "log"
    SUMMARY = "summary"
    REPORT = "report"
    MODEL = "model"
    MANIFEST = "manifest"
    METADATA = "metadata"
    SCRIPT = "script"
    ENVIRONMENT = "environment"


class ReviewStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    RESOLVED = "resolved"


class ReviewRoundMode(StrEnum):
    SINGLE_PASS = "single_pass"
    MODERATED_PANEL = "moderated_panel"


class ReviewParticipantType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class ReviewRoundStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchMode(StrEnum):
    LITERATURE_RESEARCH = "literature_research"
