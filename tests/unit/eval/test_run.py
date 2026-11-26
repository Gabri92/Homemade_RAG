"""What run_experiment adds to the parts: the cost of a run."""

from pathlib import Path

from homerag.config import load_experiment
from homerag.eval.parts import run_generation
from homerag.eval.run import run_cost
from tests.conftest import EVAL_INDEX, GOLDEN_QUESTIONS, FakeLLM, answer_or_verdict, fake_resources

CFG = load_experiment(Path("configs/experiments/baseline.yaml"))


def test_run_cost_counts_cached_answers_as_not_paid_now() -> None:
    llm = FakeLLM(answer_or_verdict)
    runs = run_generation(GOLDEN_QUESTIONS, fake_resources(EVAL_INDEX, llm, CFG.language_gate), CFG)

    assert run_cost(runs) == {"answers": 0.03, "judge": 0.06, "paid_now": 0.06}
