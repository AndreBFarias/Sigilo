"""Interface web local do Sigilo (Streamlit).

A interface só monta widgets e chama core/ e main — zero lógica de carimbo
aqui (geometria de clique e fantasma vêm de core.preview, puro e testado).
Sidebar: a chapa do selo (campos que persistem em ~/.config/sigilo).
Área principal: o documento da vez (upload, preview, assinatura, resultado).
"""
import hashlib
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
        st.header('Chapa do selo')
        campos = cfg['campos']
        titulo = st.text_input('Título', value=campos['titulo'])
        nome = st.text_input('Nome', value=campos['nome'])
        verifique = st.text_input('Verifique em', value=campos['verifique_em'],
                                  placeholder='vazio = linha oculta')
        logo = st.text_input('Logo (caminho da imagem)', value=cfg['logo'])
        if logo and not Path(logo).exists():
            st.caption('Arquivo de logo não encontrado — o selo sai sem logo.')
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


def _resetar_documento(resumo: str, pagina_inicial: int) -> None:
    """Documento novo: zera página, ponto clicado e resultado anterior."""
    st.session_state['doc_hash'] = resumo
    st.session_state['pagina_atual'] = pagina_inicial
    st.session_state['ponto_livre'] = None
    st.session_state['resultado'] = None


def _caixa_do_ponto(ponto: 'tuple[float, float, int]', cfg: dict,
                    page_rect: fitz.Rect) -> fitz.Rect:
    """Box clampado do carimbo centrado no ponto clicado."""
    caixa = preview.box_centrado(ponto[0], ponto[1],
                                 float(cfg['largura']), float(cfg['altura']))
    return preview.clampar_box(caixa, page_rect)


def _montar_preview(doc: fitz.Document, cfg: dict, resumo: str) -> None:
    """Preview sempre visível: fantasma na posição efetiva, navegação e
    clique para reposicionar no modo livre."""
    total = len(doc)
    pagina_atual = min(st.session_state['pagina_atual'], total - 1)
    page = doc[pagina_atual]
    livre = cfg['posicao'] == 'livre'

    indice_padrao, caixa_padrao = preview.box_padrao(
        doc, float(cfg['largura']), float(cfg['altura']))
    ponto = st.session_state.get('ponto_livre')

    caixa_fantasma = None
    if livre and ponto is not None and ponto[2] == pagina_atual:
        caixa_fantasma = _caixa_do_ponto(ponto, cfg, page.rect)
    elif not livre and pagina_atual == indice_padrao:
        caixa_fantasma = caixa_padrao

    imagem = preview.renderizar_pagina(page)
    if caixa_fantasma is not None:
        imagem = preview.desenhar_fantasma(imagem, caixa_fantasma, page.rect)

    if livre:
        st.caption('Clique na página para posicionar o centro do carimbo.')
        # use_column_width: a imagem preenche a coluna e o clique devolve o
        # tamanho exibido — a conversão para pontos PDF vale em qualquer tela.
        clique = streamlit_image_coordinates(
            imagem, use_column_width='always',
            key=f'clique_{resumo}_{pagina_atual}', cursor='crosshair')
        if clique is not None:
            x_pdf, y_pdf = preview.clique_para_ponto_pdf(
                clique['x'], clique['y'], clique['width'], clique['height'],
                page.rect)
            novo = (x_pdf, y_pdf, pagina_atual)
            if st.session_state.get('ponto_livre') != novo:
                st.session_state['ponto_livre'] = novo
                st.rerun()
    else:
        st.image(imagem, width='stretch')

    coluna_ant, coluna_rotulo, coluna_prox = st.columns([1, 2, 1])
    if coluna_ant.button('Anterior', disabled=pagina_atual == 0,
                         width='stretch'):
        st.session_state['pagina_atual'] = pagina_atual - 1
        st.rerun()
    coluna_rotulo.markdown(
        f"<p style='text-align:center'>{pagina_atual + 1} / {total}</p>",
        unsafe_allow_html=True)
    if coluna_prox.button('Próxima', disabled=pagina_atual >= total - 1,
                          width='stretch'):
        st.session_state['pagina_atual'] = pagina_atual + 1
        st.rerun()


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
    st.set_page_config(page_title='Sigilo', layout='wide')
    _inicializar_logging()
    aplicar_tema()

    if 'config' not in st.session_state:
        st.session_state['config'] = config.carregar()

    cfg_editado = _montar_sidebar(st.session_state['config'])

    st.title('Sigilo')
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
                indice_inicial, _ = preview.box_padrao(
                    doc, float(cfg_editado['largura']),
                    float(cfg_editado['altura']))
                _resetar_documento(resumo, indice_inicial)
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
