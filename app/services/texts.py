from app.config_loader import get_config


def render(key: str, **values) -> str:
    """Preenche o modelo de frase `key` (config/phrases.yaml). KeyError se a chave não existe."""
    return get_config().phrases[key].format(**values)
