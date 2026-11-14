"""Respostas de exemplo no formato final, para o frontend trabalhar em paralelo.

Cada rota real que substitui um exemplo apaga a entrada correspondente daqui.
"""
from datetime import date, datetime

from app.models.climate import ClimateResponse, ClimateSeries, DailyValue
from app.models.maps import LegendItem, MapLayerIndex, MapPeriod
from app.models.quiz import Question, QuizOption
from app.models.regional import CausesResponse, CauseYear, LossRanking, LossRankingItem
from app.models.reports import Report, ReportSection, ReportSummary
from app.models.rotation import CriterionScore, RotationOptionResult, RotationResponse
from app.models.satellite import SatelliteSeries
from app.models.signals import Signal, SignalsResponse

_DAYS = [DailyValue(date=date(2026, 11, d), value=v)
         for d, v in [(1, 0.0), (2, 1.2), (3, 0.4), (4, None)]]

CLIMATE = ClimateResponse(
    plot_id=1, start=date(2026, 11, 1), end=date(2026, 11, 4),
    series=[ClimateSeries(variable="PRECTOTCORR", unit="mm/day", source="NASA POWER",
                          values=_DAYS)],
)

SIGNALS = SignalsResponse(
    plot_id=1, reference_date=date(2026, 11, 12), reference_date_adjusted=False,
    signals=[
        Signal(kind="rain", color="yellow", value=22.4, normal=30.1, deviation_pct=-25.6,
               unit="mm", window_days=30, source="NASA POWER",
               message="Choveu 22.4 mm nos últimos 30 dias, 25.6% abaixo da média (30.1 mm). "
                       "Fique atento: a lavoura pode sentir falta de água."),
        Signal(kind="soil_moisture", color="green", value=0.52, normal=0.5, deviation_pct=4.0,
               unit="1", window_days=7, source="NASA POWER",
               message="O solo está com 52% de umidade na raiz, dentro do esperado para a época "
                       "(média de 50%). Sem alerta."),
    ],
)

SATELLITE = SatelliteSeries(plot_id=1, layer="ndvi", unit="1", source="NASA MODIS",
                            values=[DailyValue(date=date(2026, 10, 1), value=0.41),
                                    DailyValue(date=date(2026, 10, 17), value=0.44)])

ROTATION = RotationResponse(
    plot_id=1,
    options=[
        RotationOptionResult(
            crops=["sorgo", "feijao_caupi"], total=71.5, rank=1,
            scores=[CriterionScore(name="water", score=68.0, source="NASA POWER",
                                   detail="Chuva cobre 68% da necessidade de água."),
                    CriterionScore(name="soil", score=80.0, source="NASA MODIS",
                                   detail="NDVI médio recente de 0.44."),
                    CriterionScore(name="regional_loss", score=70.0, source="IBGE PAM",
                                   detail="Perda média de 30% na região.")]),
        RotationOptionResult(
            crops=["milho", "feijao"], total=58.0, rank=2,
            scores=[CriterionScore(name="water", score=52.0, source="NASA POWER",
                                   detail="Chuva cobre 52% da necessidade de água."),
                    CriterionScore(name="soil", score=60.0, source="NASA MODIS",
                                   detail="NDVI médio recente de 0.44."),
                    CriterionScore(name="regional_loss", score=62.0, source="IBGE PAM",
                                   detail="Perda média de 38% na região.")]),
    ],
    verdict="A melhor opção para este talhão é sorgo → feijão-caupi, com nota 71.5 de 100.",
)

LOSSES = LossRanking(
    level="region", territory_code="2", territory_name="Nordeste", period=(2010, 2023),
    source="IBGE PAM",
    items=[LossRankingItem(crop="Milho (em grão)", mean_loss_pct=24.0, worst_year=2012,
                           worst_loss_pct=41.0, years=14),
           LossRankingItem(crop="Feijão (em grão)", mean_loss_pct=22.0, worst_year=2012,
                           worst_loss_pct=39.0, years=14)],
)

CAUSES = CausesResponse(
    territory_name="Aquidabã (SE)", crop="milho",
    years=[CauseYear(year=2012, loss_pct=41.0, rain_anomaly_pct=-48.0)],
    message="Em 2012, a perda de milho foi de 41% e a chuva na estação ficou 48% abaixo do normal.",
)

MAP = MapLayerIndex(
    layer="ndvi", unit="1",
    legend=[LegendItem(color="#d73027", label="0.0"), LegendItem(color="#1a9850", label="0.8")],
    periods=[MapPeriod(period="2026-10", url="/static/maps/ndvi/2026-10.png",
                       bounds=[[-10.45, -37.25], [-10.10, -36.85]])],
)

_SECTION = ReportSection(title="Condição atual", text=SIGNALS.signals[0].message, data={})
REPORT = Report(id=1, plot_id=1, kind="analysis", title="Análise do Talhão 1",
                created_at=datetime(2026, 11, 14, 12, 0), sections=[_SECTION])
REPORT_SUMMARY = ReportSummary(**REPORT.model_dump(exclude={"sections"}))

QUIZ = [Question(id="irrigacao", text="Sua lavoura tem irrigação?",
                 options=[QuizOption(id="sim", label="Sim"), QuizOption(id="nao", label="Não")])]
