"""Gera o fixture de regressão tests/fixtures/type0_2paginas.pdf.

Monta um DOCX PII-free de duas páginas (corpo acentuado genérico na página 1,
quebra de página, corpo + linha-âncora "Brasília/DF" no RODAPÉ da página 2) e
converte via LibreOffice headless — exatamente a rota que produz os relatórios
reais do dono. O ponto crítico: o LibreOffice embute a fonte do corpo como um
SUBSET ESTRANGEIRO (prefixo tipo 'BAAAAA+DejaVuSans') na página 0. Re-subsetear
esse subset com `doc.subset_fonts()` é o que corrompia os glifos (regressão da
Sprint UX-05). O subtipo exato (Type0/Identity-H no ambiente do autor do spec,
TrueType neste ambiente) depende da versão/config do LibreOffice; o que importa
para a regressão é ser um subset estrangeiro que `subset_fonts` corrompe — a
prova dura do teste é o pixmap byte-idêntico da página sem selo, não o rótulo.

O fixture PRECISA vir pronto no repo: o CI mínimo pode não ter `soffice`, e o
teste de regressão (`tests/test_stamper.py`) lê o PDF commitado, não regenera.

A âncora fica no RODAPÉ da página 2 para o selo caber acima dela na própria
página (âncora perto do topo empurraria o box do selo para y negativo, jogando
o texto do selo para fora da página — verificado empíricamente).

Uso: venv/bin/python3 scripts/gerar_fixture_type0.py
Idempotente: sobrescreve o fixture com o mesmo conteúdo determinístico.
"""
import shutil
import subprocess
import tempfile
import xml.sax.saxutils as saxutils
import zipfile
from pathlib import Path

import fitz

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / 'tests' / 'fixtures' / 'type0_2paginas.pdf'

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

# Corpo fictício e sem PII, farto em acentos PT-BR (á, ã, ç, é, í, ó, ú, â, ê, ô,
# à) para que o LibreOffice embuta a fonte do corpo (subset estrangeiro) na pág 0.
PARAGRAFOS_PAG1 = (
    'Relatório de demonstração — conteúdo integralmente fictício.',
    'Este documento sintético serve apenas para a suíte de regressão do Sigilo. '
    'Não há informações reais, nomes verdadeiros nem endereços de terceiros.',
    'A avaliação técnica considerou proporção, âncora, coesão e revisão ortográfica '
    'com acentuação íntegra: coração, gestão, três, você, órgão, indivíduo, memória.',
    'A conclusão é única: preservar a fidelidade tipográfica do documento original '
    'após a selagem eletrônica, sem colapsar glifos das fontes estrangeiras.',
)
# Corpo da página 2 antes da âncora — empurra a âncora para o rodapé, deixando o
# selo caber acima dela na própria página.
PARAGRAFOS_PAG2 = (
    'Considerações finais do relatório fictício, sem qualquer dado pessoal.',
    'As seções anteriores demonstram a coerência do formato e a integridade da '
    'acentuação após a conversão headless.',
    'Encerra-se a demonstração reafirmando que nenhuma informação sensível consta '
    'neste artefato de teste.',
)
LINHA_ANCORA = 'Brasília/DF, 3 de julho de 2026.'


def _paragrafo(texto: str) -> str:
    return (f'<w:p><w:r><w:t xml:space="preserve">'
            f'{saxutils.escape(texto)}</w:t></w:r></w:p>')


def _documento_xml() -> str:
    pag1 = ''.join(_paragrafo(p) for p in PARAGRAFOS_PAG1)
    quebra = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    pag2 = ''.join(_paragrafo(p) for p in PARAGRAFOS_PAG2)
    ancora = _paragrafo(LINHA_ANCORA)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{pag1}{quebra}{pag2}{ancora}</w:body></w:document>'
    )


def _montar_docx(caminho: Path) -> Path:
    with zipfile.ZipFile(caminho, 'w') as pacote:
        pacote.writestr('[Content_Types].xml', CONTENT_TYPES)
        pacote.writestr('_rels/.rels', RELS)
        pacote.writestr('word/document.xml', _documento_xml())
    return caminho


def gerar() -> Path:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    perfil = Path.home() / '.cache' / 'sigilo-libreoffice'
    with tempfile.TemporaryDirectory(prefix='sigilo-fixture-') as pasta:
        docx = _montar_docx(Path(pasta) / 'type0_2paginas.docx')
        subprocess.run(
            ['soffice', '--headless',
             f'-env:UserInstallation=file://{perfil}',
             '--convert-to', 'pdf', '--outdir', pasta, str(docx)],
            capture_output=True, text=True, timeout=180, check=False,
        )
        pdf = Path(pasta) / 'type0_2paginas.pdf'
        if not pdf.exists():
            raise RuntimeError('LibreOffice não converteu o DOCX do fixture.')
        shutil.copyfile(pdf, DESTINO)  # /tmp e o repo podem estar em devices distintos
    return DESTINO


def _verificar(pdf: Path) -> None:
    doc = fitz.open(pdf)
    try:
        assert doc.page_count == 2, f'esperado 2 páginas, obtido {doc.page_count}'
        # subset estrangeiro embutido: basefont com prefixo 'XXXXXX+' (o que
        # subset_fonts corrompe); o subtipo (Type0/TrueType) varia por ambiente.
        embutidas = [f[3] for f in doc[0].get_fonts() if '+' in f[3]]
        assert embutidas, (
            f'página 0 sem fonte estrangeira embutida (subset): {doc[0].get_fonts()}')
        assert 'Brasília/DF' in doc[1].get_text(), 'âncora ausente na página 1'
        assert 'Brasília/DF' not in doc[0].get_text(), (
            'âncora vazou para a página 0 — o selo cairia na página errada')
    finally:
        doc.close()
    print(f'fixture OK: {pdf} — 2 páginas, subset estrangeiro na pág 0 '
          f'({embutidas}), âncora só na pág 1')


if __name__ == '__main__':
    caminho = gerar()
    _verificar(caminho)
