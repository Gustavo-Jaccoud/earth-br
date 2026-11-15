from app.clients.power import PowerClient, PowerUnavailable
from app.config_loader import QuizConfig, get_config
from app.models.farms import Farm, Plot
from app.models.quiz import QuizAnswers
from app.models.reports import ReportSection
from app.models.rotation import RotationRequest
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.services import reports, rotation
from app.services.texts import render

MEDIUM_FROM, HIGH_FROM = 34, 67


class QuizError(ValueError):
    pass


Answer = str | list[str]


def _chosen(question, answer: Answer) -> list:
    """Options picked for a question (rank questions carry no risk or suggestion)."""
    if question.type == "rank":
        return []
    ids = [answer] if isinstance(answer, str) else answer
    return [o for o in question.options if o.id in ids]


def validate(answers: dict[str, Answer], quiz: QuizConfig) -> None:
    """QuizError (naming the question) for a missing answer, an unknown question or an option
    that does not fit the question type."""
    known = {q.id: q for q in quiz.questions}
    for extra in sorted(set(answers) - set(known)):
        raise QuizError(f"Unknown question: {extra}.")
    for question in quiz.questions:
        if question.id not in answers:
            raise QuizError(f"Question '{question.id}' has no answer.")
        answer, ids = answers[question.id], [o.id for o in question.options]
        ok = {
            "single": isinstance(answer, str) and answer in ids,
            "multi": isinstance(answer, list) and bool(answer) and set(answer) <= set(ids)
            and len(set(answer)) == len(answer),
            "rank": isinstance(answer, list) and sorted(answer) == sorted(ids),
        }[question.type]
        if not ok:
            raise QuizError(f"Invalid answer for '{question.id}' ({question.type}). "
                            f"Options: {', '.join(ids)}.")


def _risk(answers: dict[str, Answer], quiz: QuizConfig) -> tuple[int, str]:
    chosen = max_risk = 0
    for question in quiz.questions:
        if question.type == "rank":
            continue
        chosen += max(o.risk for o in _chosen(question, answers[question.id]))
        max_risk += max(o.risk for o in question.options)
    risk = round(100 * chosen / max_risk) if max_risk else 0
    level = "high" if risk >= HIGH_FROM else "medium" if risk >= MEDIUM_FROM else "low"
    return risk, level


def _suggestions(answers: dict[str, Answer], quiz: QuizConfig) -> list[str]:
    return [o.suggestion for question in quiz.questions
            for o in _chosen(question, answers[question.id]) if o.suggestion]


def recommendations_section(plot: Plot, farm: Farm, power: PowerClient, rasters: RasterStore,
                            gaez: GaezRepository) -> ReportSection:
    """Rotation comparison saved with the report: the current practice against rotations built
    from the crops that suit the field."""
    title = "Crop recommendations"
    options, current = rotation.recommended_options(plot, gaez)
    if len(options) < 2:
        return reports.unavailable_section(title)
    try:
        result = rotation.compare(plot, farm, RotationRequest(options=options), power, rasters,
                                  gaez)
    except PowerUnavailable:
        return reports.unavailable_section(title)
    return ReportSection(title=title, text=result.verdict,
                         data={**result.model_dump(mode="json"), "current": current})


def evaluate(plot: Plot, farm: Farm, answers: QuizAnswers, power: PowerClient,
             rasters: RasterStore, gaez: GaezRepository) -> list[ReportSection]:
    quiz = get_config().quiz
    validate(answers.answers, quiz)
    risk, level = _risk(answers.answers, quiz)
    suggestions = _suggestions(answers.answers, quiz)
    return [
        ReportSection(title="Risk", text=render(f"quiz.risk.{level}", risk=risk),
                      data={"risk": risk, "level": level, "answers": answers.answers}),
        reports.condition_section(plot, None, power, rasters, title="Environmental impact"),
        recommendations_section(plot, farm, power, rasters, gaez),
        ReportSection(
            title="Suggestions",
            text="\n".join(f"• {s}" for s in suggestions) or render("quiz.no_suggestions"),
            data={"suggestions": suggestions}),
    ]
