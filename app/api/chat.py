from fastapi import APIRouter, Depends

from app.api.deps import (
    get_farm_or_404_for_plot,
    get_gaez,
    get_plot_or_404,
    get_power_client,
    get_rasters,
)
from app.clients.power import PowerClient
from app.models.chat import ChatAnswer, ChatIntro, ChatMessage
from app.models.farms import Farm, Plot
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.services import chat

router = APIRouter(tags=["assistente"])


@router.get("/chat/suggestions")
def chat_intro() -> ChatIntro:
    """Greeting and starter questions for an empty chat."""
    return chat.intro()


@router.post("/plots/{plot_id}/chat")
def ask(
    body: ChatMessage,
    plot: Plot = Depends(get_plot_or_404),
    farm: Farm = Depends(get_farm_or_404_for_plot),
    power: PowerClient = Depends(get_power_client),
    rasters: RasterStore = Depends(get_rasters),
    gaez: GaezRepository = Depends(get_gaez),
) -> ChatAnswer:
    """Demo assistant (no AI): finds the topic of the question by keywords and answers with a
    pre-written text filled with the field's real data. When the data is missing the answer is
    the topic's fixed text (`used_data: false`); an unrelated question gets a generic answer
    (`topic: "generic"`). Texts and keywords live in `app/config/chat.yaml`."""
    return chat.reply(body.message, chat.Context(plot, farm, power, rasters, gaez))
