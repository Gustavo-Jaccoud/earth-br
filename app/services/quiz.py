from app.clients.power import PowerClient, PowerUnavailable
from app.config_loader import QuizConfig, get_config
from app.models.farms import Plot
from app.models.quiz import QuizAnswers
from app.models.reports import ReportSection
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.services import reports, water
from app.services.texts import render

MEDIUM_FROM, HIGH_FROM = 34, 67


class QuizError(ValueError):
    pass


def validate(answers: dict[str, str], quiz: QuizConfig) -> None:
    """QuizError (em português, citando a pergunta) se faltar resposta, sobrar pergunta ou a
    opção não existir."""
    known = {q.id: q for q in quiz.questions}
    for extra in sorted(set(answers) - set(known)):
        raise QuizError(f"Pergunta desconhecida: {extra}.")
    for question in quiz.questions:
        if question.id not in answers:
            raise QuizError(f"Falta responder a pergunta '{question.id}'.")
        if answers[question.id] not in {o.id for o in question.options}:
            valid = ", ".join(o.id for o in question.options)
            raise QuizError(f"Resposta inválida para '{question.id}'. Opções: {valid}.")


def _risk(answers: dict[str, str], quiz: QuizConfig) -> tuple[int, str]:
    chosen = max_risk = 0
    for question in quiz.questions:
        options = {o.id: o for o in question.options}
        chosen += options[answers[question.id]].risk
        max_risk += max(o.risk for o in question.options)
    risk = round(100 * chosen / max_risk) if max_risk else 0
    level = "high" if risk >= HIGH_FROM else "medium" if risk >= MEDIUM_FROM else "low"
    return risk, level


def _suggestions(answers: dict[str, str], quiz: QuizConfig) -> list[str]:
    found = []
    for question in quiz.questions:
        option = next(o for o in question.options if o.id == answers[question.id])
        if option.suggestion:
            found.append(option.suggestion)
    return found


def _financial(plot: Plot, answers: dict[str, str], power: PowerClient,
               gaez: GaezRepository) -> ReportSection:
    """Perda média por ano por falta de água: área × rendimento atingível (GAEZ) × fração da
    necessidade de água que a chuva não cobriu, na média de 2001-2020 (POWER) × preço."""
    title = "Impacto financeiro"
    crop = next((c for c in get_config().crops if c.id == answers.get("cultura")), None)
    lon, lat = plot.centroid
    found = gaez.at(crop.gaez_name, lat, lon) if crop else None
    if not (crop and crop.price_brl_per_kg and found):
        return ReportSection(title=title, text=render("quiz.no_financial"), data={})
    try:
        history = power.history(lat, lon)
    except PowerUnavailable:
        return ReportSection(title=title, text=render("quiz.no_financial"), data={})
    by_year = water.yearly_coverage(water.sequence_months([crop]), history)
    coverage = sum(by_year.values()) / len(by_year)
    estimate = plot.area_ha * found[1] * (1 - coverage / 100) * crop.price_brl_per_kg
    value = f"{estimate:,.0f}".replace(",", ".")
    return ReportSection(
        title=title,
        text=render("quiz.financial", value=value, area=f"{plot.area_ha:.1f}",
                    crop=crop.name.lower()),
        data={"estimated_loss_brl_per_year": round(estimate), "crop": crop.id,
              "attainable_yield_kg_ha": found[1], "water_coverage_pct": round(coverage, 1)},
    )


def evaluate(plot: Plot, answers: QuizAnswers, power: PowerClient, rasters: RasterStore,
             gaez: GaezRepository) -> list[ReportSection]:
    quiz = get_config().quiz
    validate(answers.answers, quiz)
    risk, level = _risk(answers.answers, quiz)
    suggestions = _suggestions(answers.answers, quiz)
    return [
        ReportSection(title="Risco", text=render(f"quiz.risk.{level}", risk=risk),
                      data={"risk": risk, "level": level, "answers": answers.answers}),
        reports.condition_section(plot, None, power, rasters, title="Impacto ambiental"),
        _financial(plot, answers.answers, power, gaez),
        ReportSection(
            title="Sugestões",
            text="\n".join(f"• {s}" for s in suggestions) or render("quiz.no_suggestions"),
            data={"suggestions": suggestions}),
    ]
