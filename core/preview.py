"""Matemática de preview e posicionamento do carimbo — pura, sem Streamlit.

A interface converte cliques e desenha fantasmas SEMPRE por aqui, para que
qualquer troca futura de UI herde a mesma geometria testada.
"""
import io
import logging
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageOps

from core.stamper import ANCORA_GAP, box_canto, encontrar_ancora

logger = logging.getLogger(__name__)

DPI_PREVIEW = 96
COR_FANTASMA = (189, 147, 249)  # roxo Dracula (#BD93F9)
IMAGENS = {'.png', '.jpg', '.jpeg'}


def abrir_documento(caminho: Path) -> fitz.Document:
    """Abre PDF diretamente; imagem vira documento de 1 página (1 px = 1 pt),
    espelhando a conversão de carimbar_imagem — o clique no preview de uma
    foto mapeia para os mesmos pontos que o carimbo final usa."""
    if caminho.suffix.lower() not in IMAGENS:
        return fitz.open(caminho)
    imagem = ImageOps.exif_transpose(Image.open(caminho))
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')
    doc = fitz.open()
    page = doc.new_page(width=imagem.width, height=imagem.height)
    page.insert_image(page.rect, stream=buffer.getvalue())
    return doc


def renderizar_pagina(page: fitz.Page, dpi: int = DPI_PREVIEW) -> Image.Image:
    """Renderiza a página como PIL.Image RGB (direto dos samples, sem PNG)."""
    if page.rotation != 0:
        logger.warning('Página com rotação %s graus: o preview pode divergir '
                       'do carimbo final.', page.rotation)
    pix = page.get_pixmap(dpi=dpi)
    return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def clique_para_ponto_pdf(x_img: float, y_img: float,
                          largura_exibida: float, altura_exibida: float,
                          page_rect: fitz.Rect) -> 'tuple[float, float]':
    """Converte o clique (pixels da imagem exibida) para pontos do PDF.

    O componente de clique devolve coordenadas na própria imagem exibida —
    sem letterbox e sem inversão de Y (PyMuPDF também usa origem no topo).
    """
    return (x_img * page_rect.width / largura_exibida,
            y_img * page_rect.height / altura_exibida)


def box_centrado(x_pdf: float, y_pdf: float, largura: float,
                 altura: float) -> fitz.Rect:
    """Box do carimbo com o centro no ponto clicado."""
    return fitz.Rect(x_pdf - largura / 2, y_pdf - altura / 2,
                     x_pdf + largura / 2, y_pdf + altura / 2)


def clampar_box(box: fitz.Rect, page_rect: fitz.Rect) -> fitz.Rect:
    """Desloca o box para dentro da página; limita ao tamanho dela se maior."""
    largura = min(box.width, page_rect.width)
    altura = min(box.height, page_rect.height)
    x0 = min(max(box.x0, page_rect.x0), page_rect.x1 - largura)
    y0 = min(max(box.y0, page_rect.y0), page_rect.y1 - altura)
    return fitz.Rect(x0, y0, x0 + largura, y0 + altura)


def box_padrao(doc: fitz.Document, largura: float, altura: float,
               margem: float = 36.0) -> 'tuple[int, fitz.Rect]':
    """(página, box) onde o carimbo cai SEM clique: âncora ou canto.

    Espelha a aritmética de core.stamper.carimbar_pdf (âncora 'Brasília/DF'
    centrada; senão canto inferior direito da última página). A deriva entre
    as duas é vigiada por teste que usa as constantes importadas do stamper.
    """
    ancora = encontrar_ancora(doc)
    if ancora:
        indice, linha = ancora
        page_rect = doc[indice].rect
        x0 = (page_rect.width - largura) / 2
        y1 = linha.y0 - ANCORA_GAP
        return indice, fitz.Rect(x0, y1 - altura, x0 + largura, y1)
    indice = len(doc) - 1
    return indice, box_canto(doc[indice].rect, largura, altura, margem)


def desenhar_fantasma(imagem: Image.Image, box: fitz.Rect,
                      page_rect: fitz.Rect,
                      cor: 'tuple[int, int, int]' = COR_FANTASMA,
                      opacidade: int = 77) -> Image.Image:
    """Devolve NOVA imagem com retângulo translúcido onde o selo vai cair."""
    escala_x = imagem.width / page_rect.width
    escala_y = imagem.height / page_rect.height
    pixels = (box.x0 * escala_x, box.y0 * escala_y,
              box.x1 * escala_x, box.y1 * escala_y)
    base = imagem.convert('RGBA')
    camada = Image.new('RGBA', base.size, (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)
    desenho.rectangle(pixels, fill=(*cor, opacidade), outline=(*cor, 255),
                      width=2)
    return Image.alpha_composite(base, camada).convert('RGB')
