import fitz
import pytest
from PIL import Image

from core.preview import (box_centrado, box_padrao, clampar_box,
                          clique_para_ponto_pdf, desenhar_fantasma,
                          renderizar_pagina)
from core.stamper import ANCORA_GAP

A4 = fitz.Rect(0, 0, 595, 842)


def test_clique_para_ponto_pdf_centro():
    x, y = clique_para_ponto_pdf(350, 495, 700, 990, A4)
    assert x == pytest.approx(297.5)
    assert y == pytest.approx(421.0)


def test_clique_para_ponto_pdf_cantos():
    assert clique_para_ponto_pdf(0, 0, 700, 990, A4) == (0.0, 0.0)
    x, y = clique_para_ponto_pdf(700, 990, 700, 990, A4)
    assert x == pytest.approx(595.0)
    assert y == pytest.approx(842.0)


def test_box_centrado():
    box = box_centrado(100, 200, 165, 45)
    assert (box.x0, box.y0, box.x1, box.y1) == (17.5, 177.5, 182.5, 222.5)
    assert ((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2) == (100, 200)


def test_clampar_dentro_e_bordas():
    dentro = fitz.Rect(100, 100, 265, 145)
    assert clampar_box(dentro, A4) == dentro
    direita = clampar_box(fitz.Rect(500, 100, 665, 145), A4)
    assert direita.x1 == pytest.approx(595)
    assert direita.width == pytest.approx(165)
    inferior = clampar_box(fitz.Rect(100, 820, 265, 865), A4)
    assert inferior.y1 == pytest.approx(842)
    negativo = clampar_box(fitz.Rect(-50, -20, 115, 25), A4)
    assert (negativo.x0, negativo.y0) == (0, 0)


def test_clampar_selo_maior_que_pagina():
    caixa = clampar_box(fitz.Rect(0, 0, 700, 900), A4)
    assert (caixa.x0, caixa.y0) == (0, 0)
    assert caixa.width == pytest.approx(595)
    assert caixa.height == pytest.approx(842)


def test_box_padrao_com_ancora():
    doc = fitz.open()
    doc.new_page()
    pagina = doc.new_page()
    pagina.insert_text(fitz.Point(200, 700),
                       'Brasília/DF, 3 de julho de 2026.', fontsize=14)
    indice, box = box_padrao(doc, 165, 45)
    linha = doc[1].search_for('Brasília/DF')[0]
    assert indice == 1
    assert box.y1 == pytest.approx(linha.y0 - ANCORA_GAP)
    assert (box.x0 + box.x1) / 2 == pytest.approx(doc[1].rect.width / 2)
    assert box.width == pytest.approx(165)
    assert box.height == pytest.approx(45)
    doc.close()


def test_box_padrao_sem_ancora():
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    indice, box = box_padrao(doc, 165, 45)
    r = doc[1].rect
    assert indice == 1
    assert box.x1 == pytest.approx(r.x1 - 36)
    assert box.y1 == pytest.approx(r.y1 - 36)
    doc.close()


def test_renderizar_pagina_dimensoes():
    doc = fitz.open()
    page = doc.new_page()
    imagem = renderizar_pagina(page, dpi=96)
    assert imagem.mode == 'RGB'
    assert abs(imagem.width - page.rect.width * 96 / 72) <= 1
    assert abs(imagem.height - page.rect.height * 96 / 72) <= 1
    doc.close()


def test_desenhar_fantasma_pinta_dentro_preserva_fora():
    imagem = Image.new('RGB', (595, 842), (255, 255, 255))
    box = fitz.Rect(100, 100, 265, 145)
    com_fantasma = desenhar_fantasma(imagem, box, A4)
    assert com_fantasma.getpixel((180, 120)) != (255, 255, 255)
    assert com_fantasma.getpixel((50, 50)) == (255, 255, 255)
    assert imagem.getpixel((180, 120)) == (255, 255, 255)
