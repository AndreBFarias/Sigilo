#!/usr/bin/env python3
import logging
import subprocess
import sys
from pathlib import Path

from core.config import carregar
from core.logger import setup_logging
from core.stamper import carimbar_imagem, carimbar_pdf, docx_para_pdf

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / 'Assinados'
IMAGENS = {'.png', '.jpg', '.jpeg'}
SUPORTADOS = {'.pdf', '.docx'} | IMAGENS
CACHE_CONVERSAO = Path.home() / '.cache' / 'sigilo' / 'convertidos'


def preparar_pdf(caminho: 'str | Path') -> Path:
    """Valida a entrada e devolve o PDF pronto para carimbar.

    DOCX é convertido via LibreOffice com cache por mtime: reconverte só se o
    .docx for mais novo que o PDF em cache — o preview e a assinatura reusam
    a mesma conversão.
    """
    entrada = Path(caminho).expanduser().resolve()
    if not entrada.exists():
        raise FileNotFoundError(entrada)
    if entrada.suffix.lower() not in SUPORTADOS:
        raise ValueError(f'Formato ainda não suportado: {entrada.suffix}')
    if entrada.suffix.lower() != '.docx':
        return entrada  # PDFs e imagens não precisam de conversão prévia
    pdf = CACHE_CONVERSAO / (entrada.stem + '.pdf')
    if pdf.exists() and pdf.stat().st_mtime >= entrada.stat().st_mtime:
        return pdf
    return docx_para_pdf(entrada, CACHE_CONVERSAO)


def assinar_arquivo(caminho: 'str | Path', pagina: 'int | None' = None,
                    box: 'tuple[float, float, float, float] | None' = None) -> Path:
    """Assina em Assinados/<stem>_assinado.pdf (sobrescreve se já existir).

    pagina/box: posicionamento livre vindo da interface (clique no preview);
    None mantém o fluxo da âncora automática.
    """
    cfg = carregar()
    logo = cfg['logo']
    entrada = Path(caminho).expanduser().resolve()
    if entrada.suffix.lower() in IMAGENS:
        if not entrada.exists():
            raise FileNotFoundError(entrada)
        destino = SAIDA / (entrada.stem.replace(' ', '_')
                           + '_assinado' + entrada.suffix.lower())
        return carimbar_imagem(entrada, destino, cfg['campos'], logo=logo,
                               largura=cfg['largura'], altura=cfg['altura'],
                               box=box)
    pdf = preparar_pdf(entrada)
    destino = SAIDA / (pdf.stem.replace(' ', '_') + '_assinado.pdf')
    return carimbar_pdf(pdf, destino, cfg['campos'], logo=logo,
                        largura=cfg['largura'], altura=cfg['altura'],
                        pagina=pagina, box=box)


def main() -> int:
    setup_logging()
    logger = logging.getLogger(__name__)
    if len(sys.argv) > 1:
        destino = assinar_arquivo(sys.argv[1])
        print(f'Assinado: {destino}')
        return 0
    logger.info('Nenhum arquivo passado; abrindo a interface no navegador.')
    return subprocess.call(['bash', str(RAIZ / 'scripts' / 'abrir_app.sh')])


if __name__ == '__main__':
    sys.exit(main())
