"""Tema visual do Sigilo: injeção CSS sobre o tema Dracula do config.toml.

Direção: cartório arcano — display gravada nos títulos, mono nos dados e o
lacre vermelho como único acento quente da interface (o momento de assinar).
Se a máquina estiver offline, os imports de fonte degradam para os fallbacks.
"""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=JetBrains+Mono:wght@400;600&display=swap');

/* Display gravada: identidade de selo oficial nos títulos */
h1, h2, h3 {
    font-family: 'Cinzel', 'Georgia', serif !important;
    letter-spacing: 0.06em;
}

/* Dados (caminhos, timestamp, futuro hash do SaaS) sempre em mono */
code, .sigilo-dado {
    font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace !important;
}

/* O momento do lacre: o único vermelho da interface */
button[kind="primary"]:not(:disabled), [data-testid="stBaseButton-primary"]:not(:disabled) {
    background-color: #FF5555 !important;
    border-color: #FF5555 !important;
    color: #F8F8F2 !important;
}
button[kind="primary"]:not(:disabled):hover, [data-testid="stBaseButton-primary"]:not(:disabled):hover {
    background-color: #E64747 !important;
    border-color: #E64747 !important;
}
button[kind="primary"]:disabled {
    opacity: 0.45;
    cursor: not-allowed;
}

/* Sem cromo de nuvem num app local: esconde Deploy e menu padrão */
[data-testid="stAppDeployButton"], #MainMenu {
    visibility: hidden;
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

@media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
}
</style>
"""


def aplicar_tema() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
