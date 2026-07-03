import io
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Layout clonado do selo gov.br por engenharia reversa (2026-07-02):
# o selo oficial é um bitmap 440x120px escalado para 165x45pt; as medidas
# abaixo foram extraídas pixel a pixel e os tamanhos de fonte calculados
# pela largura das linhas (métrica Helvetica).
REF_LARGURA, REF_ALTURA = 165.0, 45.0
LOGO_BOX = (0.0, 11.2, 40.9, 29.6)  # bbox do logo no referencial 165x45
X_TEXTO = 45.0                       # início do bloco de texto
# (campo, fonte, tamanho pt, baseline pt) no referencial 165x45
LAYOUT = (
    ('titulo', 'helv', 5.70, 7.10),
    ('nome', 'hebo', 4.81, 18.38),
    ('data', 'helv', 5.42, 27.00),
    ('verifique', 'helv', 5.85, 33.30),
)

ANCORA_TEXTO = 'Brasília/DF'
ANCORA_GAP = 17.3  # pt entre a base do selo e a linha âncora (padrão gov)


def timestamp_agora() -> str:
    # Formato idêntico ao selo oficial: sem espaço antes do fuso.
    return datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S%z')


def docx_para_pdf(docx: Path, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    logger.info('Convertendo %s para PDF via LibreOffice...', docx.name)
    # UserInstallation isolado: sem ele o headless falha se o LibreOffice
    # estiver aberto na sessão gráfica. soffice retorna exit 0 mesmo em
    # falha de carga, então a prova é o PDF existir.
    perfil = Path.home() / '.cache' / 'sigilo-libreoffice'
    resultado = subprocess.run(
        ['soffice', '--headless',
         f'-env:UserInstallation=file://{perfil}',
         '--convert-to', 'pdf', '--outdir', str(outdir), str(docx)],
        capture_output=True, text=True, timeout=180,
    )
    pdf = outdir / (docx.stem + '.pdf')
    if not pdf.exists():
        logger.error('soffice stdout: %s | stderr: %s',
                     resultado.stdout.strip(), resultado.stderr.strip())
        raise RuntimeError(
            'LibreOffice não converteu o DOCX (ver app.log). Contorno: '
            'exporte o PDF manualmente (ONLYOFFICE ou Google Docs) e '
            'assine o PDF direto.'
        )
    return pdf


def encontrar_ancora(doc: fitz.Document):
    """Localiza a página de assinatura (linha 'Brasília/DF, ...').

    Retorna (índice da página, rect da linha) ou None.
    """
    for i, page in enumerate(doc):
        hits = page.search_for(ANCORA_TEXTO)
        if hits:
            return i, hits[0]
    return None


def _ajustar_fonte(texto: str, fonte: str, fs: float, max_w: float) -> float:
    largura = fitz.get_text_length(texto, fontname=fonte, fontsize=fs)
    return fs if largura <= max_w else fs * max_w / largura


def box_canto(page_rect: fitz.Rect, largura: float, altura: float,
              margem: float = 36.0) -> fitz.Rect:
    """Canto inferior direito, com clamp para páginas pequenas (ex.: fotos):
    reduz a margem e escala o selo para caber dentro de page_rect.
    Compartilhado com core.preview para o fantasma nunca divergir do carimbo.
    """
    m = margem
    if largura + 2 * m > page_rect.width or altura + 2 * m > page_rect.height:
        m = max(2.0, 0.05 * min(page_rect.width, page_rect.height))
        logger.warning('Página pequena: margem reduzida para %.1f pt.', m)
    fator = min(1.0, (page_rect.width - 2 * m) / largura,
                (page_rect.height - 2 * m) / altura)
    la, al = largura * fator, altura * fator
    return fitz.Rect(page_rect.x1 - m - la, page_rect.y1 - m - al,
                     page_rect.x1 - m, page_rect.y1 - m)


def carimbar_pdf(pdf_in: Path, pdf_out: Path, campos: dict,
                 logo: str = '', largura: float = 165.0,
                 altura: float = 45.0, margem: float = 36.0,
                 pagina: 'int | None' = None,
                 box: 'fitz.Rect | None' = None) -> Path:
    """Aplica o carimbo com o layout proporcional do selo gov.br.

    campos: titulo, nome, verifique_em — todos editáveis pela interface.
    Linhas vazias não são escritas, mas o slot vertical fica reservado
    (geometria estável: o "Verifique em" do futuro SaaS já tem lugar).
    Redimensionar largura/altura escala logo, fontes e espaçamentos
    proporcionalmente ao selo de referência 165x45.
    Posição: box explícito (posicionamento livre, clique no preview) vence;
    senão âncora 'Brasília/DF'; senão canto inferior direito da página.
    """
    doc = fitz.open(pdf_in)
    if box is not None:
        page = doc[pagina if pagina is not None else -1]
        box = fitz.Rect(box)
    else:
        ancora = encontrar_ancora(doc) if pagina is None else None
        if ancora:
            idx, linha = ancora
            page = doc[idx]
            x0 = (page.rect.width - largura) / 2
            y1 = linha.y0 - ANCORA_GAP
            box = fitz.Rect(x0, y1 - altura, x0 + largura, y1)
        else:
            page = doc[pagina if pagina is not None else -1]
            box = box_canto(page.rect, largura, altura, margem)

    ex = box.width / REF_LARGURA
    ey = box.height / REF_ALTURA
    ef = min(ex, ey)  # fontes escalam pelo menor eixo (sem distorção)

    if logo and Path(logo).exists():
        slot = fitz.Rect(box.x0 + LOGO_BOX[0] * ex, box.y0 + LOGO_BOX[1] * ey,
                         box.x0 + LOGO_BOX[2] * ex, box.y0 + LOGO_BOX[3] * ey)
        # keep_proportion do insert_image NÃO preserva a razão sem rotação
        # (verificado no PyMuPDF 1.28): encaixa manualmente, centrado no slot.
        pix_logo = fitz.Pixmap(str(logo))
        fator_logo = min(slot.width / pix_logo.width,
                         slot.height / pix_logo.height)
        meia_l = pix_logo.width * fator_logo / 2
        meia_a = pix_logo.height * fator_logo / 2
        cx, cy = (slot.x0 + slot.x1) / 2, (slot.y0 + slot.y1) / 2
        alvo = fitz.Rect(cx - meia_l, cy - meia_a, cx + meia_l, cy + meia_a)
        page.insert_image(alvo, filename=str(logo))

    x_texto = box.x0 + X_TEXTO * ex
    max_w = box.x1 - x_texto - 2 * ex
    verifique = campos.get('verifique_em', '')
    valores = {
        'titulo': campos.get('titulo', ''),
        'nome': campos.get('nome', ''),
        'data': f'Data: {timestamp_agora()}',
        'verifique': f'Verifique em {verifique}' if verifique else '',
    }
    for campo, fonte, fs, baseline in LAYOUT:
        texto = valores[campo]
        if not texto:
            continue
        fs = _ajustar_fonte(texto, fonte, fs * ef, max_w)
        page.insert_text(fitz.Point(x_texto, box.y0 + baseline * ey),
                         texto, fontsize=fs, fontname=fonte)

    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    # deflate: sem isso o logo entra como RGB cru e infla o PDF em ~1 MB.
    doc.save(pdf_out, deflate=True, deflate_images=True, garbage=3)
    doc.close()
    logger.info('Carimbo aplicado: %s', pdf_out)
    return pdf_out


def carimbar_imagem(img_in: Path, img_out: Path, campos: dict,
                    logo: str = '', largura: float = 165.0,
                    altura: float = 45.0, margem: float = 36.0,
                    box: 'fitz.Rect | None' = None) -> Path:
    """Carimba PNG/JPG reutilizando carimbar_pdf (1 px = 1 pt).

    A imagem vira PDF de uma página, recebe o MESMO selo proporcional e
    volta para imagem com exatamente as dimensões em pixels do original.
    As fontes renderizam a 72 dpi — em fotos grandes o selo fica
    proporcionalmente pequeno; ajuste largura/altura ou use box.
    """
    imagem = ImageOps.exif_transpose(Image.open(img_in))
    tem_alpha = (imagem.mode in ('RGBA', 'LA')
                 or (imagem.mode == 'P' and 'transparency' in imagem.info))
    dpi = imagem.info.get('dpi')
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')

    with tempfile.TemporaryDirectory(prefix='sigilo-img-') as pasta:
        entrada = Path(pasta) / 'entrada.pdf'
        doc = fitz.open()
        page = doc.new_page(width=imagem.width, height=imagem.height)
        page.insert_image(page.rect, stream=buffer.getvalue())
        doc.save(entrada)
        doc.close()
        selado = Path(pasta) / 'selado.pdf'
        carimbar_pdf(entrada, selado, campos, logo=logo, largura=largura,
                     altura=altura, margem=margem, box=box)
        with fitz.open(selado) as saida:
            sufixo = img_out.suffix.lower()
            pix = saida[0].get_pixmap(alpha=tem_alpha and sufixo == '.png')
            if dpi:
                pix.set_dpi(round(dpi[0]), round(dpi[1]))
            img_out.parent.mkdir(parents=True, exist_ok=True)
            if sufixo in ('.jpg', '.jpeg'):
                pix.save(img_out, jpg_quality=95)
            else:
                pix.save(img_out)
    logger.info('Carimbo aplicado: %s', img_out)
    return img_out
