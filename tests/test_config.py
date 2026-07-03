"""Testes de core.config — persistência da logo do selo.

Isolam CONFIG_DIR/CONFIG_PATH em tmp_path via monkeypatch: nunca tocam o
~/.config/sigilo real do usuário.
"""
import io
from pathlib import Path

from PIL import Image

from core import config


def _isolar(monkeypatch, tmp_path: Path) -> Path:
    destino = tmp_path / 'sigilo'
    monkeypatch.setattr(config, 'CONFIG_DIR', destino)
    monkeypatch.setattr(config, 'CONFIG_PATH', destino / 'config.json')
    return destino


def _png(largura: int = 10, altura: int = 10) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGBA', (largura, altura), (189, 147, 249, 255)).save(
        buffer, format='PNG')
    return buffer.getvalue()


def test_salvar_logo_grava_copia(monkeypatch, tmp_path):
    """A cópia é gravada em CONFIG_DIR e o conteúdo bate com os bytes."""
    destino = _isolar(monkeypatch, tmp_path)
    dados = _png()
    caminho = Path(config.salvar_logo(dados, '.png'))
    assert caminho.exists()
    assert caminho.read_bytes() == dados
    assert caminho.parent == destino


def test_salvar_logo_troca_extensao_remove_antiga(monkeypatch, tmp_path):
    """Enviar logo de outra extensão remove a variante antiga (só uma resta)."""
    destino = _isolar(monkeypatch, tmp_path)
    config.salvar_logo(_png(), '.png')
    config.salvar_logo(_png(), '.jpg')
    variantes = sorted(p.name for p in destino.glob('logo.*'))
    assert variantes == ['logo.jpg']


def test_remover_logo_apaga_variantes(monkeypatch, tmp_path):
    """remover_logo apaga toda variante 'logo.*' — o selo passa a sair sem logo."""
    destino = _isolar(monkeypatch, tmp_path)
    config.salvar_logo(_png(), '.png')
    config.remover_logo()
    assert list(destino.glob('logo.*')) == []
