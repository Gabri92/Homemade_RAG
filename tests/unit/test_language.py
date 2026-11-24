from pathlib import Path

import pytest

from homerag.config import LanguageGateConfig, load_experiment
from homerag.language import Detector, build_detector, is_english

GATE = load_experiment(Path("configs/experiments/baseline.yaml")).language_gate


@pytest.fixture(scope="module")
def detector() -> Detector:
    return build_detector(GATE)


@pytest.mark.parametrize(
    "text",
    [
        "How long should the base period last for a beginner?",
        "What does Zone 5b mean in the training plan?",
        "How many hours per week during Build 2?",
        "And for how long?",
    ],
)
def test_english_questions_pass(detector: Detector, text: str) -> None:
    assert is_english(text, detector, GATE)


@pytest.mark.parametrize(
    "text",
    [
        "Quanto deve durare il periodo di base per un principiante?",
        "¿Cuánto dura el período base del plan?",
        "Combien de temps dure la période de base?",
        "Wie lange dauert die Grundlagenphase im Training?",
    ],
)
def test_non_english_questions_are_blocked(detector: Detector, text: str) -> None:
    assert not is_english(text, detector, GATE)


@pytest.mark.parametrize("text", ["LTHR?", "Build 2", "zona due", "", "2025 ?!"])
def test_short_or_letterless_messages_pass(detector: Detector, text: str) -> None:
    assert is_english(text, detector, GATE)


def test_low_confidence_lets_a_non_english_message_through(detector: Detector) -> None:
    unsure = GATE.model_copy(update={"min_confidence": 1.0})

    assert is_english("Quanto deve durare il periodo di base?", detector, unsure)


def test_unknown_language_code_fails_with_a_clear_message() -> None:
    cfg = LanguageGateConfig(languages=("en", "xx"), min_words=3, min_confidence=0.5)

    with pytest.raises(ValueError, match="unknown ISO 639-1 code 'xx'"):
        build_detector(cfg)
