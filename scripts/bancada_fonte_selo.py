"""Bancada de identificação tipográfica do selo gov.br (Sprint UX-07).

Engenharia reversa visual: o selo oficial gov.br é um bitmap achatado sem fonte
extraível (confirmado: imagem inline xref=0 na página de comparação, extract_image
falha com "bad xref"). Esta bancada identifica qual fonte livre casa o bitmap por
SOBREPOSIÇÃO DE PIXELS, com pontuação objetiva por linha (IoU + razão de tinta).

Método (numpy puro, sem skimage/scipy):

1. Extrai o raster de referência do gov via page.get_pixmap(clip=<bbox do selo>,
   matrix=Matrix(k,k)) na página de comparação (a maior imagem da metade inferior,
   localizada dinamicamente, não hardcode). O selo fica em k px/pt.
2. Segmenta o raster em 4 faixas de texto (título/nome/data/verifique) por projeção
   horizontal de tinta na coluna de texto (à esquerda fica o logo gov.br, excluído).
3. Para cada candidata (família x peso) e cada linha, renderiza a MESMA string do
   gov naquele tamanho de ponto do LAYOUT, no MESMO k px/pt, e recorta a tinta.
4. Registra a candidata sobre o gov por centroide + busca fina de translação, e
   pontua por IoU dos pixels escuros (interseção sobre união) e razão de tinta.
5. Emite a Liberation atual (S0) como baseline ANTES/DEPOIS e escolhe a família de
   maior escore agregado (média ponderada pela área de tinta por linha).

Read-only sobre Assinados/: lê o PDF de comparação e grava montagens PNG só em
--saida (scratchpad/tmp). NUNCA escreve no PDF de origem.

Uso:
    python3 scripts/bancada_fonte_selo.py \
        --fontes-dir <dir com Familia-Peso.ttf> \
        --pdf <PDF de comparação> --k 8 --saida <dir de montagens>

As TTFs candidatas são adquiridas na fase de aquisição (Google Fonts GitHub, OFL/
Apache, sha256 registrado) e ficam no --fontes-dir; a fonte vencedora é empacotada
em assets/fonts/ e o selo real é re-pontuado por esta mesma régua (S1 > S0).
"""

import argparse
import logging
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('bancada')

RAIZ = Path(__file__).resolve().parent.parent
PDF_PADRAO = (RAIZ / 'Assinados' /
              '06-2026_-_Relatorio_MEC_-_G4F_-_Andre_da_Silva_Analista_de_BI'
              '_assinado_assinado.pdf')

# (campo, string do gov, tamanho pt do LAYOUT, papel do peso)
# strings transcritas do próprio bitmap gov (ground truth) para a sobreposição.
LINHAS = (
    ('titulo', 'Documento assinado digitalmente', 5.70, 'texto'),
    ('nome', 'ANDRE DA SILVA BATISTA DE FARIAS', 4.81, 'nome'),
    ('data', 'Data: 03/07/2026 11:50:00-0300', 5.42, 'texto'),
    ('verifique', 'Verifique em https://validar.iti.gov.br', 5.85, 'texto'),
)

LIMIAR_TINTA = 128         # luminância < limiar = pixel de tinta (escuro)
FRACAO_COLUNA_TEXTO = 0.26  # texto do gov começa após ~26% da largura (logo à esq)
BUSCA_REGISTRO = 8          # +/- px de busca fina no registro por translação


def extrair_raster_gov(pdf: Path, k: int) -> 'tuple[np.ndarray, tuple]':
    """Raster binário (True = tinta) do selo gov na página de comparação.

    Localiza a maior imagem da metade inferior (o selo), extrai por get_pixmap
    (clip do bbox, Matrix(k,k)) — NUNCA extract_image (falha na imagem inline).
    """
    doc = fitz.open(pdf)
    alvo = None
    idx_pagina = None
    for i, page in enumerate(doc):
        for im in page.get_image_info(xrefs=True):
            x0, y0, x1, y1 = im['bbox']
            if y0 <= page.rect.height / 2:
                continue
            area = (x1 - x0) * (y1 - y0)
            if alvo is None or area > alvo[0]:
                alvo = (area, tuple(im['bbox']), im['width'], im['height'])
                idx_pagina = i
    if alvo is None:
        doc.close()
        raise RuntimeError('Selo gov não localizado (nenhuma imagem na metade inferior).')
    _area, bbox, w_px, h_px = alvo
    page = doc[idx_pagina]
    pix = page.get_pixmap(clip=fitz.Rect(bbox), matrix=fitz.Matrix(k, k),
                          colorspace=fitz.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    doc.close()
    logger.info('Selo gov: página idx %d, bbox %s, bitmap %dx%d px, raster %dx%d @ k=%d',
                idx_pagina, [round(v, 1) for v in bbox], w_px, h_px,
                pix.width, pix.height, k)
    return arr < LIMIAR_TINTA, (idx_pagina, bbox, w_px, h_px)


def _bandas_tinta(perfil: np.ndarray, minimo: int, gap: int) -> 'list[tuple]':
    """Sequências de linhas com tinta (perfil[y] > minimo), fundindo lacunas < gap."""
    ativo = perfil > minimo
    bandas = []
    y = 0
    n = len(ativo)
    while y < n:
        if not ativo[y]:
            y += 1
            continue
        y0 = y
        while y < n and ativo[y]:
            y += 1
        y1 = y
        # funde com a banda anterior se a lacuna for pequena
        if bandas and y0 - bandas[-1][1] < gap:
            bandas[-1] = (bandas[-1][0], y1)
        else:
            bandas.append((y0, y1))
    return bandas


def segmentar_linhas(gov: np.ndarray) -> 'list[np.ndarray]':
    """Recorta as 4 linhas de texto do gov (título/nome/data/verifique).

    Restringe a coluna de texto (exclui o logo à esquerda), projeta tinta por
    linha, agrupa em bandas e devolve cada linha recortada ao seu bbox de tinta.
    """
    h, w = gov.shape
    x_ini = int(FRACAO_COLUNA_TEXTO * w)
    coluna = gov[:, x_ini:]
    perfil = coluna.sum(axis=1)
    minimo = max(2, int(0.01 * coluna.shape[1]))
    gap = max(3, h // 60)
    bandas = _bandas_tinta(perfil, minimo, gap)
    # espera 4 linhas; se sobrarem, mantém as 4 de maior tinta, em ordem vertical
    if len(bandas) > 4:
        bandas = sorted(sorted(bandas, key=lambda b: -perfil[b[0]:b[1]].sum())[:4])
    if len(bandas) != 4:
        raise RuntimeError(f'Segmentação achou {len(bandas)} bandas, esperava 4: {bandas}')
    linhas = []
    for y0, y1 in bandas:
        faixa = coluna[y0:y1]
        cols = np.where(faixa.any(axis=0))[0]
        rows = np.where(faixa.any(axis=1))[0]
        recorte = faixa[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
        linhas.append(recorte)
    return linhas


def renderizar_linha(fontfile: Path, texto: str, pt: float, k: int) -> np.ndarray:
    """Raster binário (tinta recortada) da string renderizada com a candidata,
    no mesmo k px/pt do gov, para sobreposição direta."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=40)
    page.insert_font(fontname='cand', fontfile=str(fontfile))
    page.insert_text(fitz.Point(4, 28), texto, fontsize=pt, fontname='cand')
    pix = page.get_pixmap(matrix=fitz.Matrix(k, k), colorspace=fitz.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    doc.close()
    binario = arr < LIMIAR_TINTA
    cols = np.where(binario.any(axis=0))[0]
    rows = np.where(binario.any(axis=1))[0]
    if len(cols) == 0 or len(rows) == 0:
        return np.zeros((1, 1), dtype=bool)
    return binario[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def redimensionar(a: np.ndarray, forma: tuple) -> np.ndarray:
    """Redimensiona o recorte binário para `forma` (altura, largura) via PIL
    bilinear. Normaliza tamanho/tracking entre gov e candidata para isolar a
    letterform e a proporção interna (o peso/traço relativo é preservado pelo
    reescalonamento). Re-binariza no mesmo limiar."""
    from PIL import Image
    h, w = forma
    img = Image.fromarray((a * 255).astype(np.uint8))
    red = img.resize((max(1, w), max(1, h)), Image.BILINEAR)
    return np.asarray(red) > 127


def _canvas_centroide(a: np.ndarray, forma: tuple, centro: tuple) -> np.ndarray:
    """Cola `a` num canvas de `forma` com o centroide de tinta em `centro`."""
    ys, xs = np.nonzero(a)
    cy, cx = ys.mean(), xs.mean()
    off_y = int(round(centro[0] - cy))
    off_x = int(round(centro[1] - cx))
    canvas = np.zeros(forma, dtype=bool)
    y0, x0 = off_y, off_x
    ah, aw = a.shape
    ys0, ys1 = max(0, y0), min(forma[0], y0 + ah)
    xs0, xs1 = max(0, x0), min(forma[1], x0 + aw)
    ay0, ax0 = ys0 - y0, xs0 - x0
    canvas[ys0:ys1, xs0:xs1] = a[ay0:ay0 + (ys1 - ys0), ax0:ax0 + (xs1 - xs0)]
    return canvas


def pontuar_par(gov: np.ndarray, cand: np.ndarray,
                busca: int = BUSCA_REGISTRO) -> 'tuple[float, float, np.ndarray, np.ndarray]':
    """IoU de letterform e razão de tinta (peso) entre gov e candidata.

    Normaliza a escala (redimensiona a candidata ao bbox de tinta do gov) para
    isolar a forma da letra da diferença de tamanho/tracking, registra por
    centroide + busca de translação +/-busca e devolve a IoU máxima. A razão de
    tinta (cand/gov ao bbox normalizado) identifica o PESO: ~1 casa a densidade
    de traço do gov; >1 mais pesada, <1 mais leve.

    Devolve (iou, razao_tinta, gov_no_canvas, cand_registrada).
    """
    cand = redimensionar(cand, gov.shape)
    razao_tinta = cand.sum() / max(gov.sum(), 1)
    margem = busca + 4
    forma = (gov.shape[0] + 2 * margem, gov.shape[1] + 2 * margem)
    centro = (forma[0] / 2, forma[1] / 2)
    g = _canvas_centroide(gov, forma, centro)
    c0 = _canvas_centroide(cand, forma, centro)
    melhor_iou, melhor_c = -1.0, c0
    for dy in range(-busca, busca + 1):
        cy = np.roll(c0, dy, axis=0)
        for dx in range(-busca, busca + 1):
            c = np.roll(cy, dx, axis=1)
            inter = np.logical_and(g, c).sum()
            union = np.logical_or(g, c).sum()
            iou = inter / union if union else 0.0
            if iou > melhor_iou:
                melhor_iou = iou
                melhor_c = c
    return melhor_iou, razao_tinta, g, melhor_c


def carregar_candidatas(fontes_dir: Path) -> 'dict[str, dict[str, Path]]':
    """Escaneia `Familia-Peso.ttf` em fontes_dir; ignora *-VF.ttf (variáveis)."""
    familias: 'dict[str, dict[str, Path]]' = {}
    for f in sorted(fontes_dir.glob('*.ttf')):
        base = f.stem
        if base.endswith('-VF') or '-' not in base:
            continue
        familia, peso = base.rsplit('-', 1)
        familias.setdefault(familia, {})[peso] = f
    return familias


def montar_png(gov: np.ndarray, cand: np.ndarray, destino: Path) -> None:
    """gov (vermelho) | cand (azul) | overlay (roxo = interseção) numa faixa RGB."""
    from PIL import Image
    h, w = gov.shape
    faixa = np.full((h, w, 3), 255, dtype=np.uint8)
    faixa[gov & ~cand] = (220, 60, 60)     # só gov
    faixa[cand & ~gov] = (60, 90, 220)     # só candidata
    faixa[gov & cand] = (150, 60, 190)     # sobreposição
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(faixa).save(destino)


# peso base do papel: nome com preferência por pesos pesados; texto por leves/médios
PESOS_TEXTO = ('Regular', 'Medium', 'SemiBold')
PESOS_NOME = ('SemiBold', 'Bold', 'Medium')
# config S0 do round anterior (core/stamper.py:LAYOUT): título/data/verifique
# Regular, nome Bold (a linha de referência ANTES da troca desta sprint)
S0_CONFIG = ('Regular', 'Bold', 'Regular', 'Regular')


def executar(pdf: Path, fontes_dir: Path, k: int, saida: Path) -> None:
    gov_full, _meta = extrair_raster_gov(pdf, k)
    linhas_gov = segmentar_linhas(gov_full)
    pesos_area = [float(l.sum()) for l in linhas_gov]
    total_area = sum(pesos_area)
    familias = carregar_candidatas(fontes_dir)
    logger.info('Famílias candidatas: %s', ', '.join(sorted(familias)))
    logger.info('Área de tinta por linha (peso do agregado): %s',
                {LINHAS[i][0]: round(pesos_area[i] / total_area, 3) for i in range(4)})

    # resultados[familia][peso] = {'iou': [...4], 'tinta': [...4]}
    resultados: 'dict[str, dict[str, dict]]' = {}
    for familia, pesos in sorted(familias.items()):
        resultados[familia] = {}
        for peso, fontfile in sorted(pesos.items()):
            ious, tintas = [], []
            for i, (_campo, texto, pt, _papel) in enumerate(LINHAS):
                cand = renderizar_linha(fontfile, texto, pt, k)
                iou, tinta, _g, _c = pontuar_par(linhas_gov[i], cand)
                ious.append(iou)
                tintas.append(tinta)
            resultados[familia][peso] = {'iou': ious, 'tinta': tintas}

    def agregado(ious: list) -> float:
        return sum(ious[i] * pesos_area[i] for i in range(4)) / total_area

    print('\n=== IoU de letterform por família x peso x linha (normalizado por escala) ===')
    print(f"{'familia':13} {'peso':9} {'titulo':>7} {'nome':>7} {'data':>7} "
          f"{'verif':>7} {'agreg':>7}")
    for familia in sorted(resultados):
        for peso in sorted(resultados[familia]):
            ious = resultados[familia][peso]['iou']
            print(f"{familia:13} {peso:9} " +
                  ' '.join(f'{v:7.3f}' for v in ious) + f' {agregado(ious):7.3f}')

    print('\n=== Razão de tinta cand/gov (identifica o PESO do gov; ~1 casa a densidade) ===')
    print(f"{'familia':13} {'peso':9} {'titulo':>7} {'nome':>7} {'data':>7} {'verif':>7}")
    for familia in sorted(resultados):
        for peso in sorted(resultados[familia]):
            t = resultados[familia][peso]['tinta']
            print(f"{familia:13} {peso:9} " + ' '.join(f'{v:7.3f}' for v in t))

    # config coerente por família: um peso por papel (nome pesado, texto leve/médio),
    # escolhido pela maior IoU dentro do papel; agregado da família.
    def config_familia(familia: str) -> 'tuple[list, float]':
        cands = resultados[familia]
        escolha = []
        for i, (_campo, _texto, _pt, papel) in enumerate(LINHAS):
            preferidos = PESOS_NOME if papel == 'nome' else PESOS_TEXTO
            disp = [p for p in preferidos if p in cands] or list(cands)
            p_best = max(disp, key=lambda p: cands[p]['iou'][i])
            escolha.append((p_best, cands[p_best]['iou'][i], cands[p_best]['tinta'][i]))
        return escolha, agregado([e[1] for e in escolha])

    print('\n=== Config coerente por família (peso escolhido por papel + IoU) ===')
    print(f"{'familia':13} {'titulo':>16} {'nome':>16} {'data':>16} {'verif':>16} {'agreg':>7}")
    resumo = {}
    for familia in sorted(resultados):
        escolha, agreg = config_familia(familia)
        resumo[familia] = (escolha, agreg)
        print(f"{familia:13} " +
              ' '.join(f'{p:>8}:{v:6.3f}' for p, v, _t in escolha) + f' {agreg:7.3f}')

    # S0 = Liberation na config REAL do stamper (Regular/Bold/Regular/Regular)
    lib = resultados.get('Liberation', {})
    s0_linhas = [lib[S0_CONFIG[i]]['iou'][i] for i in range(4)] if lib else None
    s0_agreg = agregado(s0_linhas) if s0_linhas else None

    print('\n=== ANTES/DEPOIS (AC3) ===')
    if s0_linhas:
        print(f"S0 (Liberation config real {S0_CONFIG}): agregado {s0_agreg:.3f} | "
              + ', '.join(f'{LINHAS[i][0]}={s0_linhas[i]:.3f}' for i in range(4)))
    livres = [f for f in resumo if f != 'Liberation']
    vencedora = max(livres, key=lambda f: resumo[f][1])
    esc, agreg = resumo[vencedora]
    print(f"VENCEDORA (maior agregado, licença livre): {vencedora} | agregado {agreg:.3f}")
    print('  pesos por linha (peso escolhido; IoU; razão de tinta vs gov):')
    for i in range(4):
        print(f"    {LINHAS[i][0]:10} {esc[i][0]:9} IoU={esc[i][1]:.3f} tinta={esc[i][2]:.3f}")
    if s0_linhas:
        ganho_ok = all(esc[i][1] >= s0_linhas[i] - 1e-6 for i in range(4)) and agreg > s0_agreg
        print(f"  S1 >= S0 nas 4 linhas e S1_agreg > S0_agreg? {'SIM' if ganho_ok else 'NÃO'}")
        for i in range(4):
            d = esc[i][1] - s0_linhas[i]
            print(f"    {LINHAS[i][0]:10} S0={s0_linhas[i]:.3f} -> S1={esc[i][1]:.3f} "
                  f"({'+' if d >= 0 else '-'}{abs(d):.3f})")

    # montagens PNG da vencedora (config coerente) e da Liberation (config real S0)
    saida.mkdir(parents=True, exist_ok=True)
    montagens = [('vencedora_' + vencedora, [e[0] for e in esc])]
    if lib:
        montagens.append(('S0_Liberation', list(S0_CONFIG)))
    for rotulo, config in montagens:
        familia = vencedora if rotulo.startswith('vencedora') else 'Liberation'
        for i, (campo, texto, pt, _papel) in enumerate(LINHAS):
            cand = renderizar_linha(familias[familia][config[i]], texto, pt, k)
            _iou, _t, g, c = pontuar_par(linhas_gov[i], cand)
            montar_png(g, c, saida / f'{rotulo}_{i}_{campo}.png')
    logger.info('Montagens PNG (gov vermelho | cand azul | overlay roxo) em %s', saida)


def main() -> None:
    ap = argparse.ArgumentParser(description='Bancada de identificação da fonte do selo gov.br')
    ap.add_argument('--pdf', type=Path, default=PDF_PADRAO,
                    help='PDF de comparação (read-only)')
    ap.add_argument('--fontes-dir', type=Path, required=True,
                    help='Diretório com as TTFs candidatas (Familia-Peso.ttf)')
    ap.add_argument('--k', type=int, default=8, help='px/pt do raster (default 8)')
    ap.add_argument('--saida', type=Path, required=True,
                    help='Diretório das montagens PNG (scratchpad/tmp)')
    args = ap.parse_args()
    executar(args.pdf, args.fontes_dir, args.k, args.saida)


if __name__ == '__main__':
    main()
