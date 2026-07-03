import io
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Raiz do repositório (core/ -> raiz) para localizar a fonte empacotada.
RAIZ = Path(__file__).resolve().parent.parent
# Fonte embutida no selo: Liberation Sans (métrica Arial ≈ Helvetica), sob
# SIL Open Font License 1.1 (ver assets/fonts/OFL.txt). Empacotada no repo
# porque o app é distribuível e não pode depender de fonte do sistema.
# A TTF é pré-subsetada em memória (fontTools) só para os glifos do selo e
# embutida via insert_font(fontbuffer=); o render fica fixo em qualquer
# visualizador e o texto continua vivo/pesquisável e vetorial (base-14 era
# substituída de forma imprevisível pelo visualizador).
FONTE_REGULAR = RAIZ / 'assets' / 'fonts' / 'LiberationSans-Regular.ttf'
FONTE_BOLD = RAIZ / 'assets' / 'fonts' / 'LiberationSans-Bold.ttf'
# Nome interno do recurso de fonte no PDF de saída (um por peso).
FONTE_REGULAR_NOME = 'sigilo-sans'
FONTE_BOLD_NOME = 'sigilo-sans-bold'

# Layout clonado do selo gov.br por engenharia reversa (2026-07-02):
# o selo oficial é um bitmap 440x120px escalado para 165x45pt; as medidas
# abaixo foram extraídas pixel a pixel e os tamanhos de fonte calculados
# pela largura das linhas (métrica Helvetica ≈ Liberation Sans, por isso as
# baselines e posições absolutas sobrevivem à troca da fonte).
REF_LARGURA, REF_ALTURA = 165.0, 45.0
LOGO_BOX = (0.0, 11.2, 40.9, 29.6)  # bbox do logo no referencial 165x45
X_TEXTO = 45.0                       # início do bloco de texto
# (campo, peso, tamanho pt, baseline pt) no referencial 165x45
LAYOUT = (
    ('titulo', 'regular', 5.70, 7.10),
    ('nome', 'bold', 4.81, 18.38),
    ('data', 'regular', 5.42, 27.00),
    ('verifique', 'regular', 5.85, 33.30),
)
# peso -> (nome interno embutido, arquivo TTF empacotado)
FONTES = {
    'regular': (FONTE_REGULAR_NOME, FONTE_REGULAR),
    'bold': (FONTE_BOLD_NOME, FONTE_BOLD),
}
# Cache de fitz.Font para medir a largura com a MESMA métrica do render:
# fitz.get_text_length só conhece a base-14; fitz.Font.text_length usa o TTF.
_FONTE_MEDIDA: 'dict[str, fitz.Font]' = {}

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


def _fonte_medida(fontfile: Path) -> fitz.Font:
    """fitz.Font (cacheado) usado só para medir a largura do texto na MESMA
    métrica da fonte embutida no render — get_text_length não a conhece."""
    chave = str(fontfile)
    if chave not in _FONTE_MEDIDA:
        _FONTE_MEDIDA[chave] = fitz.Font(fontfile=chave)
    return _FONTE_MEDIDA[chave]


def _subset_bytes(fontfile: Path, texto: str) -> bytes:
    """Subseta a TTF em memória só para os glifos de `texto` e retorna os bytes
    da fonte reduzida. Retém o cmap dos caracteres pedidos (default do
    Subsetter), para o texto do selo continuar vivo/pesquisável e sem tofu.

    Substitui doc.subset_fonts(): aqui subsetamos APENAS a fonte do selo, sem
    re-tocar as fontes estrangeiras (Type0/TrueType) do documento original — que
    subset_fonts corrompia. O subset transiente (dezenas de glifos, ~80 ms)
    fica pequeno o bastante para dispensar o subset global no save.
    """
    fonte = TTFont(str(fontfile))
    opcoes = Options()
    opcoes.notdef_outline = True            # mantém .notdef com contorno válido
    opcoes.drop_tables += ['FFTM']          # tabela FontForge não-subsetável (só ruído)
    subsetter = Subsetter(options=opcoes)
    subsetter.populate(text=texto)
    subsetter.subset(fonte)
    buffer = io.BytesIO()
    fonte.save(buffer)
    return buffer.getvalue()


def _ajustar_fonte(texto: str, fonte: fitz.Font, fs: float,
                   max_w: float) -> float:
    largura = fonte.text_length(texto, fontsize=fs)
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
    # Agrupa os caracteres realmente renderizados por peso (linhas vazias não
    # entram) e embute, por peso usado, um subset em memória da fonte do selo
    # com só esses glifos. Um peso sem texto (ex.: nome='' deixa o bold sem uso)
    # não é subsetado nem embutido.
    chars_por_peso: 'dict[str, set]' = {}
    for campo, peso, _fs, _baseline in LAYOUT:
        texto = valores[campo]
        if texto:
            chars_por_peso.setdefault(peso, set()).update(texto)
    for peso, chars in chars_por_peso.items():
        nome_interno, fontfile = FONTES[peso]
        page.insert_font(fontname=nome_interno,
                         fontbuffer=_subset_bytes(fontfile, ''.join(chars)))
    for campo, peso, fs, baseline in LAYOUT:
        texto = valores[campo]
        if not texto:
            continue
        nome_interno, fontfile = FONTES[peso]
        fs = _ajustar_fonte(texto, _fonte_medida(fontfile), fs * ef, max_w)
        page.insert_text(fitz.Point(x_texto, box.y0 + baseline * ey),
                         texto, fontsize=fs, fontname=nome_interno)

    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    # NÃO chamar doc.subset_fonts() aqui: ele re-subseteava TODAS as fontes do
    # documento — inclusive os subsets estrangeiros do LibreOffice/Cairo (Type0
    # CairoFont, DejaVuSans) das páginas do documento original — e os corrompia
    # (regressão da Sprint UX-05: glifos colapsados em borrões nas páginas sem
    # selo). A fonte do selo já entra pré-subsetada em memória (fontTools, acima),
    # então garbage=4/use_objstms=1/deflate seguem cuidando do tamanho sem tocar
    # as fontes do documento; deflate_fonts comprime o stream do subset do selo.
    doc.save(pdf_out, deflate=True, deflate_images=True, deflate_fonts=True,
             garbage=4, use_objstms=1)
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
