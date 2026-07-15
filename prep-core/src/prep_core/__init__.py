"""prep-core: exam-agnostic building blocks shared by TOEFL and GRE prep tools."""
from .rubric import Rubric, Criterion
from .feedback import FeedbackEngine, WritingFeedback
from .providers import make_provider, make_fallback_provider, Provider, FallbackProvider
from .generate import QuestionGenerator
from .srs import SRS, Card
from .progress import ProgressStore
from .config import load_env
from .serverutil import install_idle_shutdown

__all__ = [
    "Rubric",
    "Criterion",
    "FeedbackEngine",
    "WritingFeedback",
    "make_provider",
    "make_fallback_provider",
    "Provider",
    "FallbackProvider",
    "QuestionGenerator",
    "SRS",
    "Card",
    "ProgressStore",
    "load_env",
    "install_idle_shutdown",
]
__version__ = "0.1.0"
