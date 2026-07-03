"""Testes do fluxo da logo na interface (ui/app.py) via streamlit AppTest.

Isolam CONFIG_DIR/CONFIG_PATH em tmp_path — nunca tocam o ~/.config real do
usuário. Reproduzem a regressão do UX-01b: "Remover logo" com um upload ainda
ativo no file_uploader não pode ser desfeito pelo rerun seguinte (antes, o
uploader re-persistia a logo a cada rerun e recriava o arquivo removido).

O CI (ci.yml) instala só pytest/PyMuPDF/Pillow; sem streamlit, o módulo inteiro
é pulado (importorskip) para não quebrar a coleta.
"""
import io
from pathlib import Path

import pytest

AppTest = pytest.importorskip('streamlit.testing.v1').AppTest

from PIL import Image  # noqa: E402

from core import config  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def _isolar(monkeypatch, tmp_path: Path) -> Path:
    destino = tmp_path / 'sigilo'
    monkeypatch.setattr(config, 'CONFIG_DIR', destino)
    monkeypatch.setattr(config, 'CONFIG_PATH', destino / 'config.json')
    return destino


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new('RGBA', (10, 10), (189, 147, 249, 255)).save(buffer, format='PNG')
    return buffer.getvalue()


def _app() -> AppTest:
    return AppTest.from_file(str(RAIZ / 'ui' / 'app.py'), default_timeout=30)


def _uploader_logo(at):
    return next(w for w in at.get('file_uploader') if w.label == 'Logo do selo')


def _variantes(destino: Path) -> list:
    return sorted(p.name for p in destino.glob('logo.*')) if destino.exists() \
        else []


def test_remover_logo_gruda_apos_rerun(monkeypatch, tmp_path):
    """Remover logo com upload ativo persiste: o rerun seguinte NÃO recria o
    arquivo no disco (regressão UX-01b)."""
    destino = _isolar(monkeypatch, tmp_path)
    at = _app()
    at.run()
    assert not at.exception
    assert _variantes(destino) == []

    _uploader_logo(at).upload('logo.png', _png())
    at.run()
    assert _variantes(destino) == ['logo.png']  # upload novo persistiu

    remover = next(b for b in at.button if b.label == 'Remover logo')
    remover.click()
    at.run()
    assert _variantes(destino) == []  # a remoção apagou o disco

    at.run()  # rerun com o upload AINDA ativo no widget
    assert _variantes(destino) == []  # não recriou — a remoção grudou


def test_upload_novo_repersiste(monkeypatch, tmp_path):
    """Enviar uma logo nova (novo file_id) volta a persistir — o gate não
    quebra o caminho feliz de upload (critério 5)."""
    destino = _isolar(monkeypatch, tmp_path)
    at = _app()
    at.run()

    _uploader_logo(at).upload('logo.png', _png())
    at.run()
    assert _variantes(destino) == ['logo.png']

    next(b for b in at.button if b.label == 'Remover logo').click()
    at.run()
    assert _variantes(destino) == []

    _uploader_logo(at).upload('outra.png', _png())
    at.run()
    assert _variantes(destino) == ['logo.png']  # persiste como 'logo<ext>'
