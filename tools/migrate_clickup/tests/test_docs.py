# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
from tools.migrate_clickup import docs as D


def test_omite_plantillas_y_vacios():
    assert D.is_skipped("Getting Started Guide", [{"content": "x" * 500}]) == "plantilla de ClickUp"
    assert D.is_skipped("Solución IM-1", [{"content": ""}]) == "vacío"
    assert D.is_skipped("Ayuda ERPTQ", [{"content": "x" * 60}]) is None


def test_subpaginas_como_secciones():
    # Páginas hermanas del primer nivel -> h1; sus hijas -> h2, h3.
    pages = [{"name": "Ayuda", "content": "Intro", "pages": [{"name": "Paso 1", "content": "uno", "pages": [{"name": "Detalle", "content": "dos"}]}]},
             {"name": "Otra", "content": "tres"}]
    out = D.doc_html(pages)
    assert out.index("Intro") < out.index("<h2>Paso 1</h2>") < out.index("<h3>Detalle</h3>") < out.index("<h1>Otra</h1>")


def test_br_de_tablas_y_html_crudo_escapado():
    out = D.to_html("| a | b |\n|---|---|\n| x<br>y | <script>z</script> |")
    assert "x<br>y" in out and "<script>" not in out


def test_imagenes_de_clickup_se_bajan(tmp_path):
    (tmp_path / "images").mkdir()

    class FakeCU:
        def download(self, url, max_bytes):
            return b"png"

    body = '<p><img alt="cap" src="https://t30902916.p.clickup-attachments.com/t1/a/imagen%20(1).png" /></p>' \
           '<p><img alt="g" src="https://www.google.com/x.png" /></p>' \
           '<p><a href="https://t30902916.p.clickup-attachments.com/t1/b/clase.mp4?view=open">video</a></p>'
    out = D.localize(body, str(tmp_path), FakeCU(), 10, print)
    assert 'data-mawesi-img="' in out and 'data-mawesi-file="' in out and "clickup-attachments" not in out
    assert 'src="https://www.google.com/x.png"' in out
    assert len(list((tmp_path / "images").iterdir())) == 2


def test_tarjeta_de_link():
    out = D.to_html("Ver [\n\nwww.java.com\n\nhttps://www.java.com/x\\_y.jsp\n\n](https://www.java.com/x_y.jsp) ya.")
    assert '<a href="https://www.java.com/x_y.jsp">www.java.com</a>' in out and "[" not in out
