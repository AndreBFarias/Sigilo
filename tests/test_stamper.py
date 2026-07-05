import hashlib
import re
import shutil
import time
import zipfile
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageChops

import main
from core.stamper import box_canto, carimbar_imagem, carimbar_pdf, \
    docx_para_pdf, timestamp_agora

# Campos explícitos: os testes não dependem do config do usuário.
CAMPOS = {'titulo': 'Documento assinado eletronicamente',
          'nome': 'FULANO DE TAL',
          'verifique_em': 'https://validar.sigilo.app'}

# Fixture commitado (LibreOffice headless): 2 páginas com fonte estrangeira
# embutida (subset) na página 0 e âncora "Brasília/DF" no rodapé da página 1.
# Gerado por scripts/gerar_fixture_type0.py; não depende de soffice em CI.
FIXTURE_TYPE0 = Path(__file__).resolve().parent / 'fixtures' / 'type0_2paginas.pdf'

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>'
)
RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>'
)
DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body><w:p><w:r><w:t>Relatório de teste do Sigilo.</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>Brasília/DF, 3 de julho de 2026.</w:t></w:r></w:p>'
    '</w:body></w:document>'
)


def _pdf_branco(caminho: Path, largura: float = 595,
                altura: float = 842) -> Path:
    doc = fitz.open()
    doc.new_page(width=largura, height=altura)
    doc.save(caminho)
    doc.close()
    return caminho


def _spans(pdf: Path) -> list:
    """(texto, x, y, tamanho) por span, ordenado por y — origin equivale ao
    ponto do insert_text (verificado no pymupdf 1.28)."""
    doc = fitz.open(pdf)
    linhas = []
    for bloco in doc[-1].get_text('dict')['blocks']:
        for linha in bloco.get('lines', []):
            for span in linha['spans']:
                linhas.append((span['text'], span['origin'][0],
                               span['origin'][1], span['size']))
    doc.close()
    return sorted(linhas, key=lambda s: s[2])


def _docx_minimo(caminho: Path) -> Path:
    with zipfile.ZipFile(caminho, 'w') as pacote:
        pacote.writestr('[Content_Types].xml', CONTENT_TYPES)
        pacote.writestr('_rels/.rels', RELS)
        pacote.writestr('word/document.xml', DOCUMENT)
    return caminho


def _foto(caminho: Path, largura: int = 400, altura: int = 300) -> Path:
    Image.new('RGB', (largura, altura), (200, 210, 230)).save(caminho)
    return caminho


def test_timestamp_formato():
    # Formato do selo oficial: sem espaço antes do fuso.
    assert re.fullmatch(
        r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}[+-]\d{4}', timestamp_agora()
    )


def test_carimbo_em_pdf(tmp_path):
    src = _pdf_branco(tmp_path / 'doc.pdf')
    out = carimbar_pdf(src, tmp_path / 'out.pdf', CAMPOS)
    doc = fitz.open(out)
    texto = doc[-1].get_text()
    doc.close()
    assert CAMPOS['nome'] in texto
    assert 'Verifique em https://validar.sigilo.app' in texto


def test_fonte_embutida_e_texto_vivo(tmp_path):
    """UX-05/UX-07: a fonte TTF fica embutida (subset), não mais a base-14
    helv/hebo, e o texto continua vivo/pesquisável (guarda contra a
    regressão para bitmap achatado). UX-07 trocou a família para a
    humanista Source Sans 3 (maior escore de sobreposição vs o selo gov.br)."""
    src = _pdf_branco(tmp_path / 'doc.pdf')
    out = carimbar_pdf(src, tmp_path / 'out.pdf', CAMPOS)
    doc = fitz.open(out)
    pagina = doc[-1]
    basefonts = [f[3] for f in pagina.get_fonts()]
    texto = pagina.get_text()
    doc.close()
    # subset embutido: basefont vem com prefixo (ex.: 'MUPTJJ+Source Sans 3')
    assert any('Source Sans 3' in n for n in basefonts)
    assert not any('Liberation' in n for n in basefonts)
    assert not any(n in ('Helvetica', 'Helvetica-Bold') for n in basefonts)
    assert 'Documento assinado eletronicamente' in texto


def test_pesos_por_linha_embutidos(tmp_path):
    """UX-07: cada linha usa o peso eleito pela bancada de sobreposição
    (título Regular, nome Bold, data/verifique Medium — o gov usa peso médio
    fora do nome). Prova via o PostScript name do span embutido em cada linha."""
    src = _pdf_branco(tmp_path / 'doc.pdf')
    out = carimbar_pdf(src, tmp_path / 'out.pdf', CAMPOS)
    doc = fitz.open(out)
    fonte_da_linha = {}
    for bloco in doc[-1].get_text('dict')['blocks']:
        for linha in bloco.get('lines', []):
            for span in linha['spans']:
                fonte_da_linha[span['text']] = span['font']
    doc.close()

    def fonte(prefixo: str) -> str:
        return next(f for t, f in fonte_da_linha.items() if t.startswith(prefixo))

    # data (timestamp) e verifique (URL) variam de conteúdo: casa por prefixo
    assert fonte('Documento assinado') == 'SourceSans3-Regular'
    assert fonte('FULANO DE TAL') == 'SourceSans3-Bold'
    assert fonte('Data:') == 'SourceSans3-Medium'
    assert fonte('Verifique em') == 'SourceSans3-Medium'


def test_nome_acentuado_sem_tofu(tmp_path):
    """UX-05: o TTF embutido cobre os glifos PT-BR — nome com acento
    renderiza íntegro (sem '?'/tofu), extraível literal do PDF."""
    campos = dict(CAMPOS, nome='JOÃO DA CONCEIÇÃO')
    src = _pdf_branco(tmp_path / 'doc.pdf')
    out = carimbar_pdf(src, tmp_path / 'out.pdf', campos)
    doc = fitz.open(out)
    texto = doc[-1].get_text()
    doc.close()
    assert 'JOÃO DA CONCEIÇÃO' in texto
    assert '?' not in texto


def test_original_intacto(tmp_path):
    src = _pdf_branco(tmp_path / 'doc.pdf')
    antes = hashlib.sha256(src.read_bytes()).hexdigest()
    out = carimbar_pdf(src, tmp_path / 'out.pdf', CAMPOS)
    assert hashlib.sha256(src.read_bytes()).hexdigest() == antes
    assert out != src and out.exists()


@pytest.mark.skipif(shutil.which('soffice') is None,
                    reason='LibreOffice ausente')
def test_conversao_docx(tmp_path):
    docx = _docx_minimo(tmp_path / 'minimo.docx')
    pdf = docx_para_pdf(docx, tmp_path / 'saida')
    assert pdf.exists()
    doc = fitz.open(pdf)
    assert 'Brasília' in doc[0].get_text()
    doc.close()


def test_layout_proporcional(tmp_path):
    """Selo 2x maior → posições e fontes exatamente 2x (layout proporcional)."""
    b1 = fitz.Rect(10, 10, 175, 55)
    b2 = fitz.Rect(10, 10, 340, 100)
    src = _pdf_branco(tmp_path / 'doc.pdf')
    out1 = carimbar_pdf(src, tmp_path / 'um.pdf', CAMPOS, box=b1)
    out2 = carimbar_pdf(src, tmp_path / 'dois.pdf', CAMPOS, box=b2)
    spans1, spans2 = _spans(out1), _spans(out2)
    assert len(spans1) == len(spans2) == 4
    for a, b in zip(spans1, spans2):
        assert b[1] - b2.x0 == pytest.approx(2 * (a[1] - b1.x0), abs=0.01)
        assert b[2] - b2.y0 == pytest.approx(2 * (a[2] - b1.y0), abs=0.01)
        assert b[3] == pytest.approx(2 * a[3], abs=0.01)


def test_campos_vazios(tmp_path):
    """Linha vazia é oculta, mas o slot fica reservado (geometria estável)."""
    box = fitz.Rect(10, 10, 175, 55)
    src = _pdf_branco(tmp_path / 'doc.pdf')
    sem = dict(CAMPOS, verifique_em='')
    out1 = carimbar_pdf(src, tmp_path / 'sem.pdf', sem, box=box)
    spans1 = _spans(out1)
    assert len(spans1) == 3
    baselines = [s[2] for s in spans1]
    assert baselines == pytest.approx([17.10, 28.38, 37.00], abs=0.01)
    out2 = carimbar_pdf(src, tmp_path / 'com.pdf', CAMPOS, box=box)
    spans2 = _spans(out2)
    assert len(spans2) == 4
    assert [s[2] for s in spans2[:3]] == pytest.approx(baselines, abs=0.01)


def test_carimbo_em_imagem(tmp_path):
    src = _foto(tmp_path / 'foto.png')
    out = carimbar_imagem(src, tmp_path / 'foto_assinado.png', CAMPOS)
    imagem = Image.open(out)
    assert imagem.size == (400, 300)
    diferenca = ImageChops.difference(Image.open(src).convert('RGB'),
                                      imagem.convert('RGB'))
    assert diferenca.getbbox() is not None  # o selo pintou pixels


def test_imagem_pequena_clampada(tmp_path):
    src = _foto(tmp_path / 'mini.png', 200, 150)
    out = carimbar_imagem(src, tmp_path / 'mini_assinado.png', CAMPOS)
    assert Image.open(out).size == (200, 150)


def test_imagem_jpeg(tmp_path):
    src = _foto(tmp_path / 'foto.jpg')
    out = carimbar_imagem(src, tmp_path / 'foto_assinado.jpg', CAMPOS)
    assert out.suffix == '.jpg'
    assert Image.open(out).size == (400, 300)


def test_box_canto_pagina_pequena():
    caixa = box_canto(fitz.Rect(0, 0, 200, 150), 165, 45)
    assert caixa.x0 >= 0 and caixa.y0 >= 0
    assert caixa.x1 <= 200 and caixa.y1 <= 150


def test_logo_letterbox(tmp_path):
    """Logo de razão diferente do slot não distorce (círculo segue círculo)."""
    logo = tmp_path / 'quadrado.png'
    Image.new('RGBA', (100, 100), (189, 147, 249, 255)).save(logo)
    src = _pdf_branco(tmp_path / 'doc.pdf')
    out = carimbar_pdf(src, tmp_path / 'out.pdf', CAMPOS, logo=str(logo),
                       box=fitz.Rect(10, 10, 175, 55))
    doc = fitz.open(out)
    info = doc[-1].get_image_info()[0]['bbox']
    doc.close()
    largura = info[2] - info[0]
    altura = info[3] - info[1]
    assert largura / altura == pytest.approx(1.0, abs=0.01)


def test_pdf_com_logo_sem_bloat(tmp_path):
    """O logo embutido é comprimido: saída < 60 KB (era 1,21 MB sem deflate)."""
    wordmark = Path(main.RAIZ) / 'assets' / 'logo_placeholder.png'
    src = _pdf_branco(tmp_path / 'doc.pdf')
    out = carimbar_pdf(src, tmp_path / 'out.pdf', CAMPOS, logo=str(wordmark))
    assert out.stat().st_size < 60_000


def test_cli_logo_vazia_sem_logo(tmp_path, monkeypatch):
    """Logo removida (cfg['logo'] == '') → o PDF final sai sem imagem embutida.

    Regressão do UX-01b: antes, main.py fazia `'' or placeholder`, reintroduzindo
    o wordmark no selo mesmo após "Remover logo". get_images() vazio prova que
    nenhuma imagem foi embutida (com logo, retornaria uma entrada)."""
    monkeypatch.setattr(main, 'SAIDA', tmp_path / 'saida')
    monkeypatch.setattr(main, 'carregar', lambda: {
        'campos': CAMPOS, 'logo': '', 'largura': 165, 'altura': 45,
        'posicao': 'ancora-assinatura'})
    src = _pdf_branco(tmp_path / 'doc.pdf')
    destino = main.assinar_arquivo(str(src))
    doc = fitz.open(destino)
    imagens = doc[0].get_images()
    doc.close()
    assert imagens == []


def test_fontes_estrangeiras_intactas_apos_selagem(tmp_path):
    """HOTFIX-01: assinar um PDF com fonte estrangeira embutida (subset do
    LibreOffice/Cairo) NÃO pode alterar as páginas que não recebem o selo.

    Fecha o buraco de cobertura da UX-05: os testes usavam PDFs sintéticos do
    fitz (só base-14/Liberation), sem fontes estrangeiras, então não pegaram
    que doc.subset_fonts() re-subseteava e corrompia os subsets do documento
    original. TEETH: com subset_fonts (código pré-fix) a página 0 corrompe
    (samples divergem); sem ele, a página 0 fica byte-idêntica."""
    campos = dict(CAMPOS, nome='JOÃO DA CONCEIÇÃO')  # nome acentuado: cobre tofu
    mat = fitz.Matrix(2, 2)
    sha_fixture = hashlib.sha256(FIXTURE_TYPE0.read_bytes()).hexdigest()
    doc_in = fitz.open(FIXTURE_TYPE0)
    # a página 0 traz a fonte estrangeira embutida (subset com prefixo 'XXXXXX+')
    embutidas = [f[3] for f in doc_in[0].get_fonts() if '+' in f[3]]
    antes = doc_in[0].get_pixmap(matrix=mat).samples
    doc_in.close()
    assert embutidas, 'fixture inválido: página 0 sem fonte estrangeira embutida'

    out = carimbar_pdf(FIXTURE_TYPE0, tmp_path / 'out.pdf', campos)

    doc_out = fitz.open(out)
    depois = doc_out[0].get_pixmap(matrix=mat).samples
    texto_selo = doc_out[1].get_text()
    doc_out.close()
    # 1) página sem selo byte-idêntica (teeth do subset_fonts)
    assert depois == antes
    # 2) selo vivo/pesquisável na página da âncora
    assert 'Documento assinado eletronicamente' in texto_selo
    # 3) nome acentuado íntegro, sem tofu
    assert 'JOÃO DA CONCEIÇÃO' in texto_selo
    assert '?' not in texto_selo
    # o fixture commitado (entrada) nunca é alterado pela selagem
    assert hashlib.sha256(FIXTURE_TYPE0.read_bytes()).hexdigest() == sha_fixture


def test_politica_sobrescrever(tmp_path, monkeypatch):
    """Saída existente é sobrescrita em silêncio (decisão do dono, 03/07)."""
    monkeypatch.setattr(main, 'SAIDA', tmp_path / 'saida')
    monkeypatch.setattr(main, 'carregar', lambda: {
        'campos': CAMPOS, 'logo': '', 'largura': 165, 'altura': 45,
        'posicao': 'ancora-assinatura'})
    src = _pdf_branco(tmp_path / 'doc.pdf')
    primeiro = main.assinar_arquivo(str(src))
    mtime1 = primeiro.stat().st_mtime
    time.sleep(1.1)  # garante Data diferente no segundo carimbo
    segundo = main.assinar_arquivo(str(src))
    assert segundo == primeiro
    assert segundo.stat().st_mtime > mtime1
