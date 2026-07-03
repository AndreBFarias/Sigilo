"""Gera o logo placeholder do carimbo (assets/logo_placeholder.png).

Wordmark "Sigilo" serif bicolor na paleta Dracula, fundo transparente — espelha
o H1 da interface (Fraunces gravada como um selo) e escapa do fundo de papel do
preview do selo, ficando direto sobre a superfície #44475A da sidebar. Corpo
"Sigi" em pergaminho e terminação "lo" em roxo, para ter contraste real sobre a
chapa (o corpo escuro anterior sumia). Placeholder até o ícone definitivo da
Sprint 3; rodar uma vez:

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
# 250 (não 285): com a serif de capital S, "Sigilo" a 285 mede ~830 px e estoura
# os 818 px do canvas; a 250 mede ~728 px, com ~45 px de folga em cada lado.
TAMANHO_FONTE = 250
PERGAMINHO = '#F8F8F2'  # Dracula: texto claro — contraste real sobre a chapa
ROXO = '#BD93F9'        # Dracula: roxo da marca
# Serif alinhada à Fraunces do H1 (o fallback declarado da Fraunces no tema é
# Georgia); a rasterização não embute a fonte, só o pixel do placeholder.
FONTES = (
    '/usr/share/fonts/truetype/msttcorefonts/Georgia_Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf',
)


def carregar_fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for caminho in FONTES:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    raise FileNotFoundError(f'Nenhuma fonte TTF encontrada em: {FONTES}')


def gerar(destino: Path = DESTINO) -> Path:
    """Desenha "Sigi" (pergaminho) + "lo" (roxo) centrados, fundo transparente."""
    imagem = Image.new('RGBA', (LARGURA, ALTURA), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    fonte = carregar_fonte(TAMANHO_FONTE)
    largura_total = desenho.textlength('Sigilo', font=fonte)
    largura_prefixo = desenho.textlength('Sigi', font=fonte)
    bbox = desenho.textbbox((0, 0), 'Sigilo', font=fonte)
    x0 = (LARGURA - largura_total) / 2
    y0 = (ALTURA - (bbox[3] - bbox[1])) / 2 - bbox[1]
    desenho.text((x0, y0), 'Sigi', font=fonte, fill=PERGAMINHO)
    desenho.text((x0 + largura_prefixo, y0), 'lo', font=fonte, fill=ROXO)
    imagem.save(destino, optimize=True)
    logger.info('Logo placeholder gerado em %s (%d px de largura)',
                destino, round(largura_total))
    return destino


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    gerar()
