# Fontes de dados

| Fonte | Produto / versão | Variável usada | Resolução | Período | Link |
|---|---|---|---|---|---|
| NASA POWER | Daily API, comunidade `AG` (MERRA-2 / SYN1DEG) | chuva corrigida (`PRECTOTCORR`), temperaturas, umidade do ar, umidade do solo na raiz (`GWETROOT`), radiação | ~0,5° (~50 km) | 1981 até ~2 dias atrás | <https://power.larc.nasa.gov/docs/services/api/temporal/daily/> |
| NASA SMAP | SPL3SMP_E v006 (L3 enhanced, 9 km) | `Soil_Moisture_Retrieval_Data_AM_soil_moisture` (m³/m³, faixa válida 0,02–0,5) | 9 km | 2015 em diante | <https://nsidc.org/data/spl3smp_e/versions/6> |
| NASA GPM | IMERG Final diário, GPM_3IMERGDF v07 | `precipitation` (mm/dia) | 0,1° (~10 km) | 1998 em diante, com atraso de meses | <https://gpm.nasa.gov/data/imerg> |
| NASA MODIS | MOD13Q1 v061 (composto de 16 dias) | `_250m_16_days_NDVI` (faixa válida −0,2 a 1,0) | 250 m | 2000 em diante | <https://lpdaac.usgs.gov/products/mod13q1v061/> |
| IBGE | Produção Agrícola Municipal (SIDRA, tabela 5457) | área plantada (8331), área colhida (216), produção (214), rendimento (112) | município | anual, 2010–2023 usados | <https://sidra.ibge.gov.br/tabela/5457> |

**Acesso:** POWER e SIDRA são abertos, sem chave. SMAP e MODIS vêm pelo
[AppEEARS](https://appeears.earthdatacloud.nasa.gov); o GPM, pelo serviço Harmony da NASA. Ambos
exigem conta gratuita no [Earthdata Login](https://urs.earthdata.nasa.gov).

## Como cada fonte é usada

- **Semáforos:** chuva dos últimos 30 dias e umidade do solo da última semana, comparadas com a
  média histórica do mesmo período. Fonte preferida: satélite (GPM/SMAP) se cobre a data e tem pelo
  menos 5 anos de histórico; senão, o POWER (2001–2020 como normal climatológica).
- **Comparador de rotação:** chuva mensal histórica do POWER contra a necessidade de água da cultura
  (coeficiente de cultura × evapotranspiração de Hargreaves-Samani, calculada com temperaturas e
  radiação do POWER); NDVI do MODIS para o vigor do solo; perda da cultura pelo IBGE.
- **Perda por cultura (IBGE):** `1 − produção / (área plantada × rendimento mediano da cultura no
  território)`, limitada entre 0 e 1. Mede quanto da produção esperada se perdeu em cada ano, e por
  isso destaca as secas (2012, 2016).

## Limitações

- O POWER tem ~50 km de resolução: talhões vizinhos recebem os mesmos números.
- Satélite só existe para a região de demonstração (Aquidabã/SE); fora dela vale o POWER.
- Coeficientes de cultura e preços em `app/config/crops.yaml` são aproximados e ilustrativos.
- Culturas sem dado no IBGE (palma forrageira, feijão-caupi) aparecem como "sem dado" na perda
  regional e não entram na pontuação.
