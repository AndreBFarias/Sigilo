"""Gera o logo placeholder do carimbo (assets/logo_placeholder.png).

Wordmark "sigilo" bicolor na paleta Dracula, fundo transparente — espelha o
espírito do wordmark gov.br no slot esquerdo do selo. Placeholder até o ícone
definitivo da Sprint 3; rodar uma vez:

    venv/bin/python3 assets/gerar_logo_placeholder.py
"""
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ / 'logo_placeholder.png'

# Slot do logo no referencial 165x45 pt: 40.9 x 18.4 pt. Geramos em 20x
# (818x368 px) para ficar nítido também no selo dobrado (330x90 pt).
LARGURA, ALTURA = 818, 368
TAMANHO_FONTE = 285
ESCURO = '#282A36'  # Dracula: fundo canônico, aqui como tinta principal
ROXO = '#BD93F9'    # Dracula: roxo da marca
# Humanista arredondada, minúscula — mesma vibe do wordmark gov.br.
FONTES = (
    '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
)


def carregar_fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for caminho in FONTES:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    raise FileNotFoundError(f'Nenhuma fonte TTF encontrada em: {FONTES}')


def gerar(destino: Path = DESTINO) -> Path:
    """Desenha "sigi" (escuro) + "lo" (roxo) centrados, fundo transparente."""
    imagem = Image.new('RGBA', (LARGURA, ALTURA), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    fonte = carregar_fonte(TAMANHO_FONTE)
    largura_total = desenho.textlength('sigilo', font=fonte)
    largura_prefixo = desenho.textlength('sigi', font=fonte)
    bbox = desenho.textbbox((0, 0), 'sigilo', font=fonte)
    x0 = (LARGURA - largura_total) / 2
    y0 = (ALTURA - (bbox[3] - bbox[1])) / 2 - bbox[1]
    desenho.text((x0, y0), 'sigi', font=fonte, fill=ESCURO)
    desenho.text((x0 + largura_prefixo, y0), 'lo', font=fonte, fill=ROXO)
    imagem.save(destino)
    logger.info('Logo placeholder gerado em %s', destino)
    return destino


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    gerar()
