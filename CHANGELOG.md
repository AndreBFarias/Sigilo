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
- Suíte de testes completa (22 testes: carimbo, proporção, campos vazios,
  imagens, letterbox, compressão, política de sobrescrita, preview e clique)
- Infraestrutura: install/uninstall, run.sh, launcher do navegador
  (porta 8511), CI, logging rotativo

### Alterado
- Projeto batizado de Sigilo (antes: assinador)
- Interface migrada de GTK4 para Streamlit (2026-07-03) — visão SaaS;
  CLI `./run.sh arquivo` inalterada
- Saída assinada existente é sobrescrita em silêncio (decisão de projeto)

### Corrigido
- LibreOffice headless: falha "source file could not be loaded" causada por
  perfil compartilhado com a sessão gráfica — resolvida com
  `-env:UserInstallation` isolado
- Logo de razão diferente do slot não distorce mais (encaixe proporcional
  manual; `keep_proportion` do PyMuPDF não preserva razão sem rotação)
- PDF assinado com logo caiu de 1,21 MB para ~25 KB (compressão deflate na
  gravação)
