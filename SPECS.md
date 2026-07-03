# Sigilo — Specs de Sprints

Selador local de documentos (PDF, DOCX, imagens) com carimbo de assinatura
eletrônica: layout proporcional de selo oficial, campos configuráveis pela
interface e timestamp do momento da execução. Python + Streamlit (interface
local no navegador; migrada de GTK4 em 03/07/2026 pela visão SaaS), GPL-3.
Pasta: `~/Desenvolvimento/sigilo` (renomeada e reinstalada em 02/07/2026;
`./install.sh` executado, app no menu).

> **Nota de identidade:** o Sigilo copia o *layout* do selo gov.br (posição,
> proporção, tipografia, espaçamento — medidos por engenharia reversa), mas
> com identidade própria: logo SEU no slot, título editável, e "Verifique em"
> apontando pro SEU serviço. Nunca o logo gov.br nem validar.iti.gov.br —
> layout não é crime, selo falsificado é.

---

## STATUS (2026-07-02 23:40) — o que JÁ ESTÁ PRONTO

| Item | Estado |
|------|--------|
| Deadline 06-2026 | ENTREGUE (assinado 23:26, posição idêntica aos meses gov) |
| `core/stamper.py` — layout clonado do selo oficial | PRONTO e validado lado a lado |
| Slot de logo (esquerda, proporcional) | PRONTO — aguardando seu ícone |
| Campos configuráveis (titulo, nome, verifique_em) | PRONTO no core; UI é a Sprint 1 |
| "Verifique em" reservado (só renderiza se preenchido) | PRONTO — slot do futuro SaaS |
| Proporção: tudo escala com largura x altura | PRONTO (testado em 2x) |
| Posicionamento livre via `box=` no core | PRONTO — falta o clique no preview (Sprint 2) |
| Âncora automática ("Brasília/DF,") | PRONTO |
| Infra completa (venv, install, CI, docs, anonimato) | PRONTA |
| Rebranding Sigilo (desktop, pyproject, README, config) | PRONTO |
| Migração da UI: GTK4 → Streamlit (decisão do dono 03/07) | PRONTA (03/07) |
| Logo placeholder + "Verifique em" validar.sigilo.app | PRONTO (03/07) |
| Sprints 1–2: campos editáveis + preview com clique | PRONTAS (03/07) |
| Sprint 3: ícone arcano + interface.png + menu | PRONTA (03/07) |
| Sprint 4: imagens PNG/JPG (+letterbox e deflate no core) | PRONTA (03/07) |
| Sprint 5: suíte completa (22 testes) + install validado | PRONTA (03/07) |
| Sprint 6: LibreOffice headless | RESOLVIDA (03/07) — ver seção |

### Medidas extraídas do selo oficial (referencial 165x45 pt)

| Elemento | Valor |
|----------|-------|
| Logo | bbox (0, 11.2) a (40.9, 29.6) |
| Início do texto | x = 45.0 |
| Título | helv 5.70 pt, baseline 7.10 |
| Nome | helv-bold 4.81 pt, baseline 18.38 |
| Data | helv 5.42 pt, baseline 27.00 |
| Verifique em | helv 5.85 pt, baseline 33.30 |
| Formato da data | `dd/mm/aaaa hh:mm:ss-0300` (sem espaço no fuso) |
| Âncora | base do selo 17.3 pt acima da linha "Brasília/DF," |

O selo oficial é um bitmap 440x120 px — o nosso é texto vetorial (fica MAIS
nítido que o original em zoom).

---

## Sprints

| Sprint | Entrega | Tempo | Dono |
|--------|---------|-------|------|
| 1 | Interface Streamlit com campos editáveis | 30 min | você |
| 2 | Posicionamento livre: clique no preview (como o gov) | 40 min | você |
| 3 | Identidade visual: ícone/logo Sigilo + assets | você que sabe | você |
| 4 | Imagens PNG/JPG | 10 min | você |
| 5 | `./install.sh` + testes completos | 15 min | você |
| 6 | Consertar LibreOffice headless | 15 min | você |
| 7 | git init + GitHub (repo Sigilo) | 10 min | você |
| 8 | Visão SaaS "validar.sigilo.app" | — | futuro |

---

## Sprint 1 — Interface Streamlit com campos editáveis (30 min)

`ui/app.py` (Streamlit; substituiu o esqueleto GTK em 03/07/2026 — visão SaaS
e stack único com o protocolo-ouroboros). A novidade: **todos os campos do
carimbo são editáveis pela interface** e persistem via `core.config`.

### Wireframe (traduzido para web)
```
+------------------+------------------------------------------+
| CHAPA DO SELO    |  Sigilo                                  |
| (sidebar)        |                                          |
| Título    [...]  |  +------------------------------------+  |
| Nome      [...]  |  | Documento (arraste ou procure)     |  |
| Verificar [...]  |  +------------------------------------+  |
| Logo      [...]  |                                          |
| L [165] A [45]   |  [           Assinar agora            ]  |  <- lacre
| (*) âncora       |                                          |
| ( ) livre        |  Assinado e salvo em Assinados/..._      |
| [pré-visualização|  assinado.pdf  [Baixar] [Abrir pasta]    |
|  viva do selo]   |                                          |
+------------------+------------------------------------------+
```

### Princípios de UX (mantidos)
1. Zero redigitação — tudo persiste em `~/.config/sigilo/config.json`.
2. Timestamp nunca é editável — sempre o `now()` do clique.
3. 1 arquivo, 1 clique, assinado. Nunca sobrescreve o original.
4. Resultado: caminho + botões, sem dialog modal.
5. Saída já existente (`_assinado.pdf`): sobrescreve em silêncio (decisão 03/07).

### Notas técnicas
- `st.file_uploader` (PDF/DOCX) com drag-and-drop nativo; bytes persistidos em
  cache por hash (`~/.cache/sigilo/uploads/`) — mtime estável entre reruns.
- Campos `st.text_input`; salvos no config ao assinar (não a cada tecla).
- Tema Dracula canônico em `.streamlit/config.toml` + CSS em `ui/tema.py`
  (lacre `#FF5555` apenas no botão Assinar).
- Launcher `scripts/abrir_app.sh`: porta fixa 8511 (8501/8590 são do
  ouroboros), kill por PID da porta, readiness poll, abre o navegador.
- CLI intacta (`./run.sh arquivo.pdf`); a UI não tem lógica de carimbo —
  só chama `core/` e `main`.
- Pré-visualização viva do carimbo na sidebar usa a MESMA rota de código do
  selo final (`carimbar_pdf` em PDF branco temporário).

---

## Sprint 2 — Posicionamento livre: clique no preview (40 min)

A feature do site do governo, só que funcionando. O core JÁ aceita
`carimbar_pdf(..., pagina=N, box=fitz.Rect(x0, y0, x1, y1))` — a sprint é
100% interface:

1. **Preview** (sempre visível com documento carregado):
   `page.get_pixmap(dpi=96)` → `PIL.Image` → `streamlit-image-coordinates`
   no modo livre (cursor crosshair) ou `st.image` no modo âncora.
2. **Navegação**: botões anterior/próxima + rótulo "5 / 16". Iniciar na
   página da âncora se existir (`core.stamper.encontrar_ancora`).
3. **Clique**: o componente devolve `{'x','y','width','height'}` em pixels
   da imagem exibida: `x_pdf = x * page.rect.width / width` (idem y; sem
   letterbox nem inversão de Y). O clique é o CENTRO do carimbo:
   `box = fitz.Rect(x - L/2, y - A/2, x + L/2, y + A/2)`.
4. **Feedback**: retângulo fantasma roxo desenhado em PIL sobre o render,
   na posição efetiva (clique no modo livre; âncora/canto caso contrário).
5. Clicou fora da página ou carimbo estouraria a borda: clampar o box
   pra dentro de `page.rect`. Matemática pura em `core/preview.py`,
   coberta por `tests/test_preview.py` (sem Streamlit).

**Aceite:** abrir PDF, navegar até qualquer página, clicar onde quiser,
assinar — carimbo aparece centrado no ponto clicado. Repetir em imagem
(quando a Sprint 4 existir) e em docx convertido.

---

## Sprint 3 — Identidade visual (você que manda)

- **Ícone/logo Sigilo**: vai no slot esquerdo do carimbo E no `.desktop`.
  Sugestão de conceito: sigilo/selo arcano na paleta Dracula (roxo #BD93F9,
  fundo #282A36) — casa com o "forjando o sigilo" do install.sh.
  O slot do carimbo é quase quadrado (40.9 x 18.4 pt área útil) — teste o
  ícone em tamanho selo (40 pt) antes de fechar o traço.
- Salvar como `assets/icon.png` (o install.sh detecta e instala sozinho).
- `assets/interface.png`: screenshot da Sprint 1 pronta, pro README.
- Definir `logo` no config apontando pro icon — o carimbo passa a usá-lo.

**Aceite:** carimbo com seu ícone renderizado nítido em 165x45 e em 330x90.

---

## Sprint 4 — Imagens PNG/JPG (10 min)

- `carimbar_imagem(...)` em `core/stamper.py` com Pillow, replicando o
  MESMO layout proporcional (LAYOUT/LOGO_BOX/X_TEXTO escalados).
- Truque pra não duplicar lógica: converter a imagem pra PDF de uma página
  (`fitz.open()` + `insert_image`) e reutilizar `carimbar_pdf`, exportando
  de volta pra imagem no final. Um caminho de código só.
- Roteador em `main.py`: incluir `.png/.jpg/.jpeg` em `SUPORTADOS`.

**Aceite:** `./run.sh foto.png` gera `foto_assinado.png` com o mesmo selo.

---

## Sprint 5 — Instalação + testes (15 min)

1. `./install.sh` (o .desktop agora chama-se `sigilo.desktop`).
2. `tests/test_stamper.py`: implementar os 3 TODOs; teste do timestamp já
   cobre o formato oficial. Adicionar: teste do layout proporcional
   (carimbo 2x → posições 2x) e teste de campos vazios (linha oculta,
   slot reservado).

> **DECIDIDO (03/07/2026):** quando o `_assinado.pdf` já existe, o Sigilo
> SOBRESCREVE em silêncio — política fixada em teste.

**Aceite:** app no menu; `venv/bin/python3 -m pytest -v` verde.

---

## Sprint 6 — Consertar LibreOffice headless (15 min)

Sintoma: "Error: source file could not be loaded" (exit 0) pra qualquer
arquivo. Descartados: AppArmor (complain), dpkg (-V limpo), perfil (env
virgem). Suspeita: dist-upgrade.

1. Teste GUI: abre docx? Exporta PDF?
2. `sudo apt install --reinstall libreoffice-core libreoffice-writer ure uno-libs-private`
3. Persistiu: `--reinstall libreoffice-common` + testar com usuário novo.
4. Validar: `soffice --headless --convert-to pdf --outdir /tmp x.txt`.

Alternativa já em uso: exportar PDF pelo ONLYOFFICE (Flatpak instalado).
O erro do app já instrui esse contorno.

> **RESOLVIDA (03/07/2026), sem reinstalar nada:** o sintoma não reproduz com
> o código atual. Causa provável do histórico: o código antigo em
> `Desenvolvimento/assinador/` chamava o soffice SEM `-env:UserInstallation`
> isolado — com o LibreOffice GUI aberto, o headless delegava à instância da
> sessão e falhava com "source file could not be loaded" (exit 0). O
> `core/stamper.py` atual isola o perfil em `~/.cache/sigilo-libreoffice`.
> Provas: teste adversarial com GUI aberto + conversão simultânea verde;
> `test_conversao_docx` sem skip; fluxo DOCX completo pela interface
> (upload → conversão → âncora → selo) verificado.

---

## Sprint 7 — git init + GitHub (10 min)

```bash
git init && git add -A && git commit -m "feat: nasce o Sigilo"
gh repo create Sigilo --public --source=. --push
```

- `anonymity-check.yml` ativo: commits limpos, sem menção de ferramenta.
- `.gitignore` protege `Docx/`, `Assinados/`, `*.docx` e arquivos anti-IA.
- Atualizar badge de estrelas do README com o repo real.

---

## Sprint 8 — Visão SaaS: validar.sigilo.app (futuro, sem prazo)

A ideia que o "Verifique em" vazio guarda: um serviço de verificação
PRÓPRIO, honesto e verificável de verdade.

- Ao assinar, o Sigilo calcula o sha256 do PDF final e registra
  (hash, nome, timestamp) no serviço; o carimbo ganha
  `Verifique em https://validar.sigilo.app/<id>`.
- A página do id mostra: hash esperado, quem, quando. Qualquer pessoa
  confere arrastando o PDF (hash bate = documento íntegro).
- Grátis pra indivíduos, plano pra empresas (times, API, webhook).
- Diferencial vs gov.br: funciona, é aberto, e o modelo de confiança é
  transparente (hash público, sem autoridade central fingida).
- Primeiro passo quando chegar a hora: registrar domínio + endpoint de
  registro/consulta (FastAPI + SQLite resolve o MVP).

---

## Backlog

- Lote: assinar vários arquivos de uma vez
- Presets de posição nomeados (inferior-direita etc.) além de âncora/livre
- Âncora configurável (outro texto além de "Brasília/DF,")
- Vendorizar `streamlit-image-coordinates` se o pacote for abandonado
  (~120 linhas + HTML/JS estático)

(Removidos em 03/07: drag-and-drop — nativo no `st.file_uploader`; modo
escuro Dracula — resolvido pelo tema do `.streamlit/config.toml`. Porta da
interface: 8511, fixa.)
