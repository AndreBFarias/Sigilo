# Changelog

## [Não lançado]

### Adicionado
- Carimbo com layout proporcional de selo oficial (engenharia reversa):
  slot de logo, título, nome, data e linha "Verifique em" configuráveis
- Âncora automática na página de assinatura ("Brasília/DF, ...")
- Posicionamento livre via box explícito (base para o clique no preview)
- Conversão automática DOCX para PDF via LibreOffice headless
- Configuração persistente em `~/.config/sigilo/config.json`
- Interface Streamlit no navegador: campos do selo editáveis com
  pré-visualização viva do carimbo, preview de páginas com navegação e
  posicionamento livre por clique (fantasma mostra onde o selo cai)
- Suporte a imagens PNG/JPG com round-trip pixel-exato (dimensões e DPI
  preservados) e selo clampado em fotos pequenas
- Logo placeholder (wordmark) e ícone arcano do aplicativo, paleta Dracula
- Linha "Verifique em" padrão apontando para https://validar.sigilo.app
- Fonte do selo embutida no PDF via TTF (Source Sans 3 Regular/Medium/Bold,
  `assets/fonts/`, SIL OFL 1.1 — release oficial Adobe source-sans 3.052R,
  compatível com GPL-3): render tipográfico determinístico em qualquer
  visualizador, texto segue vivo/pesquisável (subset embutido; PDF < 60 KB)
- Suíte de testes completa (32 testes: carimbo, proporção, campos vazios,
  imagens, letterbox, compressão, política de sobrescrita, preview, clique
  e peso da fonte por linha do selo)
- Infraestrutura: install/uninstall, run.sh, launcher do navegador
  (porta 8511), CI, logging rotativo

### Alterado
- Projeto batizado de Sigilo (antes: assinador)
- Interface migrada de GTK4 para Streamlit (2026-07-03) — visão SaaS;
  CLI `./run.sh arquivo` inalterada
- Saída assinada existente é sobrescrita em silêncio (decisão de projeto)
- Fonte do selo trocada de Liberation Sans (neo-grotesca) para Source Sans 3
  (humanista) para casar melhor o selo oficial gov.br (Sprint UX-07, round 2):
  escolha por bancada de sobreposição de pixels (IoU por linha vs o bitmap do
  gov, `scripts/bancada_fonte_selo.py`) — Source Sans 3 teve o maior escore
  agregado entre as fontes livres (0.558 vs 0.453 da Liberation). Pesos por
  linha eleitos pelo escore e pela densidade de traço do gov: título Regular,
  nome Bold, data e "Verifique em" Medium (o gov usa peso médio fora do nome).
  Mesma rota segura do HOTFIX-01 (subset em memória + `insert_font`)

### Corrigido
- LibreOffice headless: falha "source file could not be loaded" causada por
  perfil compartilhado com a sessão gráfica — resolvida com
  `-env:UserInstallation` isolado
- Logo de razão diferente do slot não distorce mais (encaixe proporcional
  manual; `keep_proportion` do PyMuPDF não preserva razão sem rotação)
- PDF assinado com logo caiu de 1,21 MB para ~25 KB (compressão deflate na
  gravação)
