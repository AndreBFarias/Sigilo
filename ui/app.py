"""Interface web local do Sigilo (Streamlit).

A interface só monta widgets e chama core/ e main — zero lógica de carimbo
aqui (geometria de clique e fantasma vêm de core.preview, puro e testado).
Sidebar: a chapa do selo (campos que persistem em ~/.config/sigilo).
Área principal: o documento da vez (upload, preview, assinatura, resultado).
"""
import hashlib
import io
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import fitz  # noqa: E402
import streamlit as st  # noqa: E402
from PIL import Image  # noqa: E402
from streamlit_image_coordinates import streamlit_image_coordinates  # noqa: E402

from core import config, preview  # noqa: E402
from core.logger import setup_logging  # noqa: E402
from core.stamper import carimbar_pdf  # noqa: E402
from main import SAIDA, assinar_arquivo, preparar_pdf  # noqa: E402
from ui.tema import aplicar_tema  # noqa: E402

logger = logging.getLogger(__name__)

CACHE_UPLOADS = Path.home() / '.cache' / 'sigilo' / 'uploads'

# Identidade visual — ponto único de troca pela arte final (um por asset).
ASSETS = RAIZ / 'assets'
ICONE = ASSETS / 'icon.png'
LOGO_MARCA = ASSETS / 'logo_placeholder.png'


@st.cache_resource
def _inicializar_logging() -> None:
    setup_logging()


@st.cache_resource
def _abrir_documento(caminho: str, mtime: float) -> fitz.Document:
    return preview.abrir_documento(Path(caminho))


def _persistir_upload(enviado) -> 'tuple[Path, str]':
    """Grava o upload em cache por hash — mtime estável entre reruns."""
    dados = enviado.getvalue()
    resumo = hashlib.sha256(dados).hexdigest()[:16]
    destino = CACHE_UPLOADS / resumo / Path(enviado.name).name
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
    return destino, resumo


def _renderizar_selo(campos: dict, logo: str, largura: float,
                     altura: float) -> Image.Image:
    """Pré-visualização viva do carimbo — mesma rota de código do selo final."""
    margem = 4.0
    with tempfile.TemporaryDirectory(prefix='sigilo-selo-') as pasta:
        branco = Path(pasta) / 'branco.pdf'
        doc = fitz.open()
        doc.new_page(width=largura + 2 * margem, height=altura + 2 * margem)
        doc.save(branco)
        doc.close()
        selado = Path(pasta) / 'selado.pdf'
        carimbar_pdf(branco, selado, campos, logo=logo, largura=largura,
                     altura=altura,
                     box=(margem, margem, margem + largura, margem + altura))
        with fitz.open(selado) as saida:
            pix = saida[0].get_pixmap(matrix=fitz.Matrix(3, 3))
            return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def _montar_sidebar(cfg: dict) -> dict:
    """Chapa do selo: campos persistentes. Devolve o config editado
    (gravado em disco somente ao assinar)."""
    with st.sidebar:
        # Logo da marca no cabeçalho da sidebar (st.logo renderiza como
        # stLogo, não stImage — escapa do fundo de papel do preview do selo).
        st.logo(str(LOGO_MARCA), size='large')
        campos = cfg['campos']
        titulo = st.text_input('Título', value=campos['titulo'])
        nome = st.text_input('Nome', value=campos['nome'])
        verifique = st.text_input('Verifique em', value=campos['verifique_em'],
                                  placeholder='vazio = linha oculta')
        # logo_atual carrega a escolha da sessão entre reruns ('' = removida);
        # sem ele, o gate por file_id pularia a re-persistência mas o valor
        # reverteria para cfg['logo'] a cada rerun (desfazendo a remoção).
        logo = st.session_state.get('logo_atual', cfg['logo'])
        enviado_logo = st.file_uploader('Logo do selo',
                                        type=['png', 'jpg', 'jpeg'])
        if (enviado_logo is not None
                and enviado_logo.file_id
                != st.session_state.get('logo_file_id')):
            # Persiste só uma vez por upload novo: reruns com o mesmo arquivo
            # no widget não recriam a logo (senão desfariam "Remover logo").
            try:
                Image.open(io.BytesIO(enviado_logo.getvalue())).verify()
            except Exception:
                logger.warning('Logo enviada inválida: %s', enviado_logo.name)
                st.warning('Imagem inválida — envie um PNG ou JPG válido.')
            else:
                logo = config.salvar_logo(
                    enviado_logo.getvalue(),
                    Path(enviado_logo.name).suffix.lower())
                st.session_state['logo_file_id'] = enviado_logo.file_id
                st.session_state['logo_atual'] = logo
        if logo and Path(logo).exists():
            st.image(logo, width=120)
            if st.button('Remover logo'):
                config.remover_logo()
                logo = ''
                st.session_state['logo_atual'] = ''
                # Marca o upload corrente como tratado: o rerun seguinte cai no
                # ramo "já persistido" e não recria o arquivo no disco.
                if enviado_logo is not None:
                    st.session_state['logo_file_id'] = enviado_logo.file_id
        else:
            st.caption('Sem logo — o selo sai sem imagem.')
        coluna_l, coluna_a = st.columns(2)
        # Mínimo 20 pt (não 50): a altura padrão do selo oficial é 45 pt.
        largura = coluna_l.number_input('Largura (pt)', min_value=20.0,
                                        max_value=400.0,
                                        value=float(cfg['largura']), step=5.0)
        altura = coluna_a.number_input('Altura (pt)', min_value=20.0,
                                       max_value=400.0,
                                       value=float(cfg['altura']), step=5.0)
        rotulos = ('Âncora de assinatura', 'Livre (clique no preview)')
        indice = 0 if cfg['posicao'] == 'ancora-assinatura' else 1
        escolha = st.radio('Posição', rotulos, index=indice)
        posicao = 'ancora-assinatura' if escolha == rotulos[0] else 'livre'

        editado = {
            **cfg,
            'campos': {'titulo': titulo, 'nome': nome,
                       'verifique_em': verifique},
            'logo': logo,
            'largura': largura,
            'altura': altura,
            'posicao': posicao,
        }

        st.subheader('Pré-visualização')
        try:
            selo = _renderizar_selo(editado['campos'], logo, largura, altura)
            st.image(selo, width='stretch')
        except Exception:
            logger.exception('Falha ao renderizar a pré-visualização do selo.')
            st.caption('Pré-visualização indisponível.')
        st.caption('A data acima é ilustrativa: o carimbo final usa o momento '
                   'do clique em Assinar — nunca editável.')
    return editado


def _resetar_documento(resumo: str) -> None:
    """Documento novo: zera ponto clicado e resultado anterior. Não há mais
    página corrente — o preview mostra todas as páginas em rolagem contínua."""
    st.session_state['doc_hash'] = resumo
    st.session_state['ponto_livre'] = None
    st.session_state['resultado'] = None


def _caixa_do_ponto(ponto: 'tuple[float, float, int]', cfg: dict,
                    page_rect: fitz.Rect) -> fitz.Rect:
    """Box clampado do carimbo centrado no ponto clicado."""
    caixa = preview.box_centrado(ponto[0], ponto[1],
                                 float(cfg['largura']), float(cfg['altura']))
    return preview.clampar_box(caixa, page_rect)


@st.cache_data(show_spinner=False)
def _pagina_png(_doc: fitz.Document, doc_hash: str, indice: int,
                dpi: int) -> bytes:
    """Render cacheado por página: reruns não re-renderizam páginas já vistas.

    O `_doc` (prefixo `_`) fica FORA da chave de cache; `doc_hash`, `indice` e
    `dpi` a compõem. O fantasma NUNCA entra aqui: ele depende do ponto/box do
    rerun e é desenhado por cima do PNG cacheado, só na página ativa.
    """
    imagem = preview.renderizar_pagina(_doc[indice], dpi)
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')
    return buffer.getvalue()


def _montar_preview(doc: fitz.Document, cfg: dict, resumo: str) -> None:
    """Preview contínuo: todas as páginas empilhadas em rolagem vertical
    (estilo assinador gov.br). O fantasma aparece na página com ponto/âncora;
    no modo livre, clicar em qualquer página reposiciona o centro do carimbo."""
    total = len(doc)
    livre = cfg['posicao'] == 'livre'

    indice_padrao, caixa_padrao = preview.box_padrao(
        doc, float(cfg['largura']), float(cfg['altura']))
    ponto = st.session_state.get('ponto_livre')

    if livre:
        st.caption('Clique em qualquer página para posicionar o centro do '
                   'carimbo.')

    for indice in range(total):
        page_rect = doc[indice].rect
        # Imagem base do cache (sem fantasma); fantasma desenhado por cima.
        imagem = Image.open(io.BytesIO(
            _pagina_png(doc, resumo, indice, preview.DPI_PREVIEW)))

        caixa_fantasma = None
        if livre and ponto is not None and ponto[2] == indice:
            caixa_fantasma = _caixa_do_ponto(ponto, cfg, page_rect)
        elif not livre and indice == indice_padrao:
            caixa_fantasma = caixa_padrao
        if caixa_fantasma is not None:
            imagem = preview.desenhar_fantasma(imagem, caixa_fantasma,
                                               page_rect)

        st.caption(f'Página {indice + 1} de {total}')
        if livre:
            # use_column_width: a imagem preenche a coluna e o clique devolve o
            # tamanho exibido — a conversão para pontos PDF vale em qualquer
            # tela. Chave por página: cada componente coexiste na rolagem.
            clique = streamlit_image_coordinates(
                imagem, use_column_width='always',
                key=f'clique_{resumo}_{indice}', cursor='crosshair')
            if clique is not None:
                # Guard idempotente POR PÁGINA: cada componente RETÉM seu último
                # clique e o reporta a cada rerun. Comparar contra ponto_livre
                # faria duas páginas clicadas guerrearem por reruns; por isso
                # comparamos o clique bruto contra o último processado desta
                # chave — só um clique realmente novo reposiciona.
                chave_clique = f'ultimo_clique_{resumo}_{indice}'
                if st.session_state.get(chave_clique) != clique:
                    st.session_state[chave_clique] = clique
                    x_pdf, y_pdf = preview.clique_para_ponto_pdf(
                        clique['x'], clique['y'], clique['width'],
                        clique['height'], page_rect)
                    st.session_state['ponto_livre'] = (x_pdf, y_pdf, indice)
                    st.rerun()
        else:
            st.image(imagem, width='stretch')


def _assinar(caminho: Path, doc: fitz.Document, cfg: dict) -> None:
    """Persiste o config e assina — com box do clique no modo livre."""
    st.session_state['config'] = cfg
    config.salvar(cfg)
    pagina: 'int | None' = None
    box: 'tuple[float, float, float, float] | None' = None
    if cfg['posicao'] == 'livre':
        ponto = st.session_state['ponto_livre']
        caixa = _caixa_do_ponto(ponto, cfg, doc[ponto[2]].rect)
        pagina = ponto[2]
        box = (caixa.x0, caixa.y0, caixa.x1, caixa.y1)
    try:
        with st.spinner('Assinando o documento...'):
            destino = assinar_arquivo(caminho, pagina=pagina, box=box)
    except Exception as exc:
        logger.exception('Falha ao assinar %s', caminho)
        st.session_state['resultado'] = None
        st.error(f'Não foi possível assinar: {exc}')
    else:
        st.session_state['resultado'] = destino


def main() -> None:
    st.set_page_config(page_title='Sigilo', page_icon=str(ICONE),
                       layout='wide')
    _inicializar_logging()
    aplicar_tema()

    if 'config' not in st.session_state:
        st.session_state['config'] = config.carregar()

    cfg_editado = _montar_sidebar(st.session_state['config'])

    st.markdown('<h1>Sigi<span style="color: #BD93F9">lo</span></h1>',
                unsafe_allow_html=True)
    st.caption('Sele documentos com o seu carimbo — o original nunca é alterado.')

    enviado = st.file_uploader('Documento',
                               type=['pdf', 'docx', 'png', 'jpg', 'jpeg'])
    caminho: 'Path | None' = None
    doc: 'fitz.Document | None' = None
    if enviado is not None:
        caminho, resumo = _persistir_upload(enviado)
        try:
            if caminho.suffix.lower() in preview.IMAGENS:
                alvo = caminho
            else:
                with st.spinner('Preparando o documento '
                                '(DOCX pode levar minutos)...'):
                    alvo = preparar_pdf(caminho)
        except Exception as exc:
            logger.exception('Falha ao preparar %s', caminho)
            st.error(f'Não foi possível preparar o documento: {exc}')
        else:
            doc = _abrir_documento(str(alvo), alvo.stat().st_mtime)
            if st.session_state.get('doc_hash') != resumo:
                _resetar_documento(resumo)
            _montar_preview(doc, cfg_editado, resumo)

    if st.button('Assinar agora', type='primary', disabled=doc is None,
                 width='stretch'):
        if (cfg_editado['posicao'] == 'livre'
                and st.session_state.get('ponto_livre') is None):
            st.error('Clique no preview para posicionar o carimbo antes de '
                     'assinar.')
        else:
            _assinar(caminho, doc, cfg_editado)

    resultado = st.session_state.get('resultado')
    if resultado and Path(resultado).exists():
        # Recibo: agrupa sucesso + ações num cartão (layout, sem lógica nova).
        with st.container(border=True):
            st.success(f'Assinado e salvo em {resultado}')
            coluna_baixar, coluna_abrir = st.columns(2)
            coluna_baixar.download_button('Baixar PDF assinado',
                                          Path(resultado).read_bytes(),
                                          file_name=Path(resultado).name,
                                          mime='application/pdf',
                                          width='stretch')
            if coluna_abrir.button('Abrir pasta Assinados', width='stretch'):
                subprocess.Popen(['xdg-open', str(SAIDA)])


main()
