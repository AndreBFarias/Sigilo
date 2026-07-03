# Guia de Contribuição -- Sigilo

## Como Contribuir

1. Fork → branch feature → PR contra `main`
2. Commits em PT-BR (Conventional Commits)

## Padrão

- PT-BR com acentuação correta
- Zero emojis, zero menção IA
- Type hints sempre
- `logging` (nunca print em produção)

## Configuração

```bash
./install.sh
```

Ou manualmente (o venv PRECISA de `--system-site-packages` para o GTK):

```bash
/usr/bin/python3 -m venv --system-site-packages venv
venv/bin/pip install -r requirements.txt
```

## Testes

```bash
venv/bin/pytest tests/ -v
```
