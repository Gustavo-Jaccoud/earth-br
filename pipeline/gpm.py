"""Baixa precipitação diária GPM IMERG Final (GPM_3IMERGDF v07) recortada na região, via Harmony.

Uso:  EDL_TOKEN=... python -m pipeline.gpm   (ou EDL_USERNAME/EDL_PASSWORD)
Pede ao Harmony, em blocos de 6 meses, só a bbox da região e junta tudo em
data/rasters/precipitation.nc (mm/dia).

ATENÇÃO: `date_chunks` e `to_layer` têm testes; o fluxo do Harmony precisa de conta Earthdata e
foi escrito pela documentação do harmony-py, sem teste ao vivo. O produto Final tem atraso de
meses (consulte `latest_available`): para datas mais recentes a API usa o NASA POWER.
Se isto não funcionar dentro do prazo, a API já cai sozinha para o POWER.
"""
import os
from datetime import date, datetime, time
from pathlib import Path

import httpx
import pandas as pd
import xarray as xr

from pipeline.layers import write_layer
from pipeline.region import load_bbox

GPM_CONCEPT_ID = "C2723754864-GES_DISC"  # GPM_3IMERGDF v07 (conferido no CMR)
CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"


def date_chunks(start: date, end: date, months: int = 6) -> list[tuple[date, date]]:
    """Divide [start, end] em blocos consecutivos, sem sobreposição, de `months` meses."""
    chunks = []
    cursor = pd.Timestamp(start)
    while cursor.date() <= end:
        chunk_end = min((cursor + pd.DateOffset(months=months) - pd.Timedelta(days=1)).date(), end)
        chunks.append((cursor.date(), chunk_end))
        cursor = pd.Timestamp(chunk_end) + pd.Timedelta(days=1)
    return chunks


def latest_available() -> date:
    """Data do granulo mais recente do GPM IMERG Final no catálogo público (CMR)."""
    response = httpx.get(CMR_GRANULES, timeout=60, params={
        "collection_concept_id": GPM_CONCEPT_ID, "page_size": 1, "sort_key": "-start_date"})
    response.raise_for_status()
    return date.fromisoformat(response.json()["feed"]["entry"][0]["time_start"][:10])


def to_layer(ds: xr.Dataset) -> xr.DataArray:
    """`precipitation` do IMERG (dims time, lon, lat) → (time, lat, lon), sem preenchimento."""
    da = ds["precipitation"].transpose("time", "lat", "lon")
    return da.where(da >= 0)


def main(start: date = date(2015, 1, 1), end: date | None = None,
         data_dir: Path = Path("data")) -> Path:
    from harmony import BBox, Client, Collection, Request  # import tardio: extra "pipeline"

    end = end or latest_available()
    west, south, east, north = load_bbox(data_dir / "region.json")
    raw = data_dir / "raw" / "gpm"
    raw.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("EDL_TOKEN")  # token do Earthdata Login (alternativa a usuário/senha)
    # Sem token: EDL_USERNAME/EDL_PASSWORD ou ~/.netrc.
    client = Client(token=token) if token else Client()
    files: list[Path] = []
    for a, b in date_chunks(start, end):
        request = Request(
            collection=Collection(id=GPM_CONCEPT_ID), spatial=BBox(west, south, east, north),
            temporal={"start": datetime.combine(a, time.min),
                      "stop": datetime.combine(b, time.max)},
            variables=["precipitation"])
        job_id = client.submit(request)
        print(f"GPM {a}..{b}: job {job_id}")
        client.wait_for_processing(job_id, show_progress=False)
        files += [Path(f.result()) for f in client.download_all(job_id, directory=str(raw))]
    days = []
    for path in sorted(files):  # um arquivo por dia; sem dask, abre e junta no tempo
        with xr.open_dataset(path) as ds:
            days.append(to_layer(ds).load())
    layer = xr.concat(days, dim="time").sortby("time")
    return write_layer(layer, "precipitation", source="NASA GPM IMERG",
                       product="GPM_3IMERGDF.07", units="mm/day", resolution="0.1 deg",
                       out_dir=data_dir / "rasters")


if __name__ == "__main__":
    main()
