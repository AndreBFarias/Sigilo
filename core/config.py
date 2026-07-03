import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / '.config' / 'sigilo'
CONFIG_PATH = CONFIG_DIR / 'config.json'
RAIZ_PROJETO = Path(__file__).resolve().parent.parent

# Todos os campos do carimbo são editáveis pela interface (Sprint 1).
PADROES = {
    'campos': {
        'titulo': 'Documento assinado eletronicamente',
        'nome': 'SEU NOME COMPLETO',
        # Placeholder do futuro SaaS de verificação; vazio = linha oculta.
        'verifique_em': 'https://validar.sigilo.app',
    },
    # Wordmark placeholder no slot esquerdo até o ícone definitivo (Sprint 3);
    # se o arquivo não existir, o carimbo sai sem logo (degradação do core).
    'logo': str(RAIZ_PROJETO / 'assets' / 'logo_placeholder.png'),
    'largura': 165,
    'altura': 45,
    'posicao': 'ancora-assinatura',  # ou 'livre' (clique no preview)
}


def carregar() -> dict:
    try:
        dados = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        campos = {**PADROES['campos'], **dados.get('campos', {})}
        return {**PADROES, **dados, 'campos': campos}
    except FileNotFoundError:
        return json.loads(json.dumps(PADROES))
    except json.JSONDecodeError:
        logger.warning('config.json corrompido, usando padrões.')
        return json.loads(json.dumps(PADROES))


def salvar(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    logger.debug('Configuração salva em %s', CONFIG_PATH)


def salvar_logo(dados: bytes, sufixo: str) -> str:
    """Persiste uma cópia da logo enviada em CONFIG_DIR e devolve o caminho.

    Remove variantes 'logo.*' de extensão diferente para não deixar cópia
    obsoleta — só existe uma logo por vez. O carimbo lê esse caminho de disco
    (contrato de core.stamper.carimbar_pdf, que degrada se o arquivo sumir).
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    destino = CONFIG_DIR / ('logo' + sufixo.lower())
    for antiga in CONFIG_DIR.glob('logo.*'):
        if antiga != destino:
            antiga.unlink()
    destino.write_bytes(dados)
    logger.debug('Logo persistida em %s (%d bytes)', destino, len(dados))
    return str(destino)


def remover_logo() -> None:
    """Apaga as variantes 'logo.*' persistidas — o selo passa a sair sem logo."""
    for antiga in CONFIG_DIR.glob('logo.*'):
        antiga.unlink()
    logger.debug('Logo removida de %s', CONFIG_DIR)
