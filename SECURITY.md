# Política de Segurança -- Sigilo

## Versões Suportadas

| Versão | Suportada |
| ------ | --------- |
| 0.1.x  | sim       |

## Dados Sensíveis

Documentos processados pelo Sigilo são relatórios e arquivos pessoais.

**Não commite** documentos reais no repositório. O `.gitignore` exclui
`Docx/`, `Assinados/` e `*.docx` — mantenha assim.

## Reportando

1. **Não** abra issue pública
2. Email ao mantenedor
3. Tempo: 48h recepção / 7d avaliação / 30d correção

## Escopo

- `core/`, `ui/`
- Scripts de instalação
- CI

## Fora do Escopo

- `PyMuPDF`, `Pillow`, LibreOffice (upstream)
