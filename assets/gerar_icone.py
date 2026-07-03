"""Gera o ícone do aplicativo (assets/icon.png).

Selo arcano na paleta Dracula: disco escuro, anel duplo roxo com quatro
pontos cardeais e a inicial "S" ao centro — o sigilo que lacra documentos.
Rodar uma vez:

    venv/bin/python3 assets/gerar_icone.py
"""
import logging
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ / 'icon.png'

TAMANHO = 512
CENTRO = TAMANHO / 2
FUNDO = '#282A36'   # Dracula: fundo canônico
ROXO = '#BD93F9'    # Dracula: roxo da marca
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


def _anel(desenho: ImageDraw.ImageDraw, raio: float, espessura: int) -> None:
    desenho.ellipse((CENTRO - raio, CENTRO - raio,
                     CENTRO + raio, CENTRO + raio),
                    outline=ROXO, width=espessura)


def _pontos_cardeais(desenho: ImageDraw.ImageDraw, raio: float,
                     tamanho: float) -> None:
    """Quatro losangos discretos entre os anéis, como marcas de um selo."""
    for angulo in (0, 90, 180, 270):
        rad = math.radians(angulo)
        cx = CENTRO + raio * math.cos(rad)
        cy = CENTRO + raio * math.sin(rad)
        desenho.polygon([(cx, cy - tamanho), (cx + tamanho, cy),
                         (cx, cy + tamanho), (cx - tamanho, cy)], fill=ROXO)


def gerar(destino: Path = DESTINO) -> Path:
    imagem = Image.new('RGBA', (TAMANHO, TAMANHO), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)

    disco = 244.0
    desenho.ellipse((CENTRO - disco, CENTRO - disco,
                     CENTRO + disco, CENTRO + disco), fill=FUNDO)
    _anel(desenho, raio=226.0, espessura=14)
    _anel(desenho, raio=188.0, espessura=5)
    _pontos_cardeais(desenho, raio=207.0, tamanho=11.0)

    fonte = carregar_fonte(250)
    bbox = desenho.textbbox((0, 0), 'S', font=fonte)
    x = CENTRO - (bbox[0] + bbox[2]) / 2
    y = CENTRO - (bbox[1] + bbox[3]) / 2
    desenho.text((x, y), 'S', font=fonte, fill=ROXO)

    imagem.save(destino)
    logger.info('Ícone gerado em %s', destino)
    return destino


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    gerar()
