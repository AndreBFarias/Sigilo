"""Tema visual do Sigilo: injeção CSS sobre o tema Dracula do config.toml.

Direção: cartório moderno — uma estação de selagem. O wordmark é o único
serif (Fraunces, gravado como um selo); toda a interface é uma grotesca
institucional (Archivo), com os títulos de seção virando rótulos em caixa-alta
marcados por um fio roxo de registro. O lacre vermelho segue como o único
acento quente (o momento de assinar). Dados (caminhos, timestamp) em mono.
Se a máquina estiver offline, os imports de fonte degradam para os fallbacks.
"""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --breu: #282A36;
    --placa: #44475A;
    --roxo: #BD93F9;
    --lacre: #FF5555;
    --pergaminho: #F8F8F2;
    --nevoa: #6272A4;
}

/* Base tipográfica: grotesca institucional (nunca monospace global) */
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
input, textarea, button, select, [data-testid="stWidgetLabel"] {
    font-family: 'Archivo', 'Helvetica Neue', system-ui, sans-serif;
}

/* Wordmark: serif de alto contraste — o selo gravado da marca */
[data-testid="stAppViewContainer"] h1 {
    font-family: 'Fraunces', 'Georgia', serif !important;
    font-weight: 600;
    font-size: 2.9rem;
    letter-spacing: -0.015em;
    line-height: 1.02;
    color: var(--pergaminho);
    margin: 0 0 0.1rem;
}

/* Rótulos de seção: eyebrow institucional com marca de registro roxa.
   Texto em pergaminho (contraste AA) e o fio roxo como acento de marca. */
h2, h3 {
    font-family: 'Archivo', sans-serif !important;
    text-transform: uppercase;
    font-size: 0.76rem !important;
    font-weight: 600;
    letter-spacing: 0.18em;
    color: var(--pergaminho) !important;
    border-left: 2px solid var(--roxo);
    padding-left: 0.6rem;
    margin: 1.8rem 0 0.4rem;
}

/* Dados (caminhos, timestamp, futuro hash do SaaS) sempre em mono */
code, .sigilo-dado {
    font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace !important;
}

/* Fita superior roxa no lugar do enfeite padrão do Streamlit */
[data-testid="stDecoration"] {
    background: linear-gradient(90deg, var(--roxo), var(--nevoa)) !important;
    height: 3px !important;
}

/* Sem cromo de nuvem num app local: esconde Deploy, menu e status */
[data-testid="stAppDeployButton"], #MainMenu, [data-testid="stStatusWidget"] {
    visibility: hidden;
}

/* Sidebar: a chapa do selo — superfície (#44475A, do config) com fio roxo à
   direita. Não sobrescrevemos o fundo: a superfície mais clara que o breu do
   main cria a profundidade da chapa e preserva o contraste do wordmark. */
[data-testid="stSidebar"] {
    border-right: 1px solid rgba(189, 147, 249, 0.28);
}

/* Área principal: coluna centrada e respirando (o documento sobre a mesa) */
[data-testid="stMainBlockContainer"], .block-container {
    max-width: 1020px;
    padding-top: 2.6rem;
    padding-bottom: 4rem;
}

/* Legendas (Página N de M, nota do selo): pergaminho esmaecido, discreto mas
   acessível. rgba(248,248,242,0.72) rende ~7,7:1 no main e ~5,4:1 na sidebar
   (AA >= 4,5:1 nas duas superfícies). A névoa fica só em fios/enfeites, nunca
   em texto pequeno (contraste 3,0:1/1,9:1 reprovaria). */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
    color: rgba(248, 248, 242, 0.72) !important;
}

/* Campos de formulário: inset suave, canto arredondado, foco roxo */
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"] {
    background: rgba(40, 42, 54, 0.6) !important;
    border-radius: 9px !important;
}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
    color: var(--pergaminho) !important;
}
[data-baseweb="input"]:focus-within {
    box-shadow: 0 0 0 3px rgba(189, 147, 249, 0.22) !important;
}

/* Uploader: alvo de arrastar com fio roxo tracejado */
[data-testid="stFileUploaderDropzone"] {
    background: rgba(40, 42, 54, 0.5) !important;
    border: 1px dashed rgba(189, 147, 249, 0.35) !important;
    border-radius: 12px !important;
    transition: border-color 140ms ease;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--roxo) !important;
}

/* O momento do lacre: o único vermelho da interface, com brilho de cera */
button[kind="primary"]:not(:disabled), [data-testid="stBaseButton-primary"]:not(:disabled) {
    background-color: var(--lacre) !important;
    border: 1px solid var(--lacre) !important;
    color: var(--breu) !important;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-size: 0.86rem;
    border-radius: 11px;
    padding: 0.72rem 1rem;
    box-shadow: 0 8px 22px -10px rgba(255, 85, 85, 0.6);
    transition: transform 130ms ease, box-shadow 130ms ease;
}
/* No hover o fundo permanece #FF5555 (nunca escurece): o texto breu sobre o
   lacre rende 4,53:1 (AA), e escurecer para #E64747 derrubaria para
   3,63:1 (sub-AA). A elevação e a sombra mais forte já comunicam o hover. */
button[kind="primary"]:not(:disabled):hover, [data-testid="stBaseButton-primary"]:not(:disabled):hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px -10px rgba(255, 85, 85, 0.72);
}
button[kind="primary"]:disabled, [data-testid="stBaseButton-primary"]:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

/* Botões secundários (Baixar, Abrir pasta, Remover logo, Enviar): discretos,
   com realce roxo no hover — nunca vermelho. */
button[kind="secondary"], [data-testid="stBaseButton-secondary"],
[data-testid="stFileUploader"] button, [data-testid="stDownloadButton"] button {
    background: transparent !important;
    border: 1px solid rgba(248, 248, 242, 0.16) !important;
    color: var(--pergaminho) !important;
    border-radius: 10px !important;
    transition: border-color 130ms ease, background 130ms ease;
}
button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover,
[data-testid="stFileUploader"] button:hover, [data-testid="stDownloadButton"] button:hover {
    border-color: var(--roxo) !important;
    background: rgba(189, 147, 249, 0.09) !important;
    color: var(--pergaminho) !important;
}

/* Foco de teclado sempre visível */
button:focus-visible, input:focus-visible, [role="radio"]:focus-visible {
    outline: 2px solid #BD93F9 !important;
    outline-offset: 2px;
}

/* Chapa do selo: a pré-visualização vive sobre papel (selo é impresso em branco) */
[data-testid="stSidebar"] [data-testid="stImage"] img {
    background: #FDFDFB;
    border: 1px solid #44475A;
    border-radius: 6px;
    padding: 8px;
}

/* Recibo: o resultado da assinatura vira um cartão sobre a superfície */
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--placa);
    border: 1px solid rgba(189, 147, 249, 0.22) !important;
    border-radius: 14px;
}

@media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
}
</style>
"""


def aplicar_tema() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
