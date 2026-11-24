"""Language gate: the first step of the pipeline (`docs/architecture.md` §4.1).

Questions are English only for now. `is_english` is a local, deterministic check with
`lingua-py`, restricted to the languages in the experiment config: a message that is clearly
in another language gets `NOTICE` and never reaches retrieval or the LLM. Doubtful messages
pass, because blocking a legitimate English question is the worst error:
- fewer than `min_words` words ("LTHR?", "Build 2"): detection is unreliable on them;
- the most likely language is not English, but below `min_confidence`.
The only module that imports `lingua`.
"""

from lingua import IsoCode639_1, Language, LanguageDetector, LanguageDetectorBuilder

from homerag.config import LanguageGateConfig

NOTICE = "I can only answer questions in English for now. Please rephrase your question in English."

# Callers annotate with this name, so `lingua` stays inside this module.
Detector = LanguageDetector


def build_detector(cfg: LanguageGateConfig) -> Detector:
    """A detector that chooses only among the configured languages. Build it once, reuse it."""
    codes = []
    for code in cfg.languages:
        try:
            codes.append(IsoCode639_1.from_str(code))
        except ValueError as error:
            raise ValueError(f"language_gate: unknown ISO 639-1 code '{code}'") from error
    return LanguageDetectorBuilder.from_iso_codes_639_1(*codes).build()


def is_english(text: str, detector: Detector, cfg: LanguageGateConfig) -> bool:
    """False only when the message is confidently in a language other than English."""
    if len(text.split()) < cfg.min_words:
        return True
    values = detector.compute_language_confidence_values(text)
    if not values:
        return True
    top = values[0]  # sorted by confidence, highest first; all 0 when there are no letters
    return top.language == Language.ENGLISH or top.value < cfg.min_confidence
