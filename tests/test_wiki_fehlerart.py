"""Art des Fehlers beim Ablegen von Dateien der Strömipedia (27.10.2026, Auftrag „letzte offene Punkte“ 4):
python tests/test_wiki_fehlerart.py  oder  pytest tests/test_wiki_fehlerart.py

Anlass: Ein Bild ließ sich auf dev nicht importieren, die Meldung sagte nur „ließ sich nicht verarbeiten“. Jetzt nennt sie
die Art – aus der Ausnahme abgeleitet, ohne deren Text (Pillow und das Dateisystem nennen Serverpfade):
  1. images.fehlerart je Art: keine Schreibrechte, Speicher voll, Dateityp nicht lesbar, Bild beschädigt oder zu groß,
     unbekannt.
  2. ZIP-Import: der Hinweis je Art (echt: unlesbar, abgeschnitten, zu viele Pixel, schreibgeschützter Ablageordner;
     nachgestellt: Speicher voll, unbekannt), kein Serverpfad im Hinweis, der Traceback im Protokoll.
  3. Einzel-Upload im Editor, Drehen und Zuschneiden: dieselbe Art in der Fehlermeldung.
Alle Seiten und Dateien sind Platzhalter."""
import errno
import io
import logging
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, UnidentifiedImageError  # noqa: E402

from test_smoke import H  # noqa: E402
from test_wiki_import import aufbau, importieren, png, seite, zip_aus  # noqa: E402

SCHREIBRECHTE = "keine Schreibrechte im Ablageordner"
VOLL = "Speicher voll"
UNLESBAR = "Dateityp nicht lesbar"
KAPUTT = "Bild beschädigt oder zu groß"
UNBEKANNT = "unbekannter Fehler – siehe Serverprotokoll"
PFAD = "/data/media/wiki/0123456789abcdef.jpg"          # so sähe ein Serverpfad im Text der Ausnahme aus


def jpeg_halb():
    """Ein JPEG, dem die zweite Hälfte fehlt – Pillow erkennt es, liest es aber nicht zu Ende."""
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()[:len(buf.getvalue()) // 2]


class Protokoll(logging.Handler):
    def __init__(self):
        super().__init__()
        self.eintraege = []

    def emit(self, record):
        self.eintraege.append(record)


def mitschreiben(app):
    h = Protokoll()
    app.logger.addHandler(h)
    return h


def hinweise(r):
    assert r.status_code == 201, r.json
    return "\n".join(r.json["hinweise"])


def test_fehlerart_je_art():
    from app.images import BildFehler, fehlerart
    for exc, art in (
        (PermissionError(errno.EACCES, "Permission denied", PFAD), SCHREIBRECHTE),
        (OSError(errno.EROFS, "Read-only file system", PFAD), SCHREIBRECHTE),
        (OSError(errno.ENOSPC, "No space left on device", PFAD), VOLL),
        (OSError(errno.EDQUOT, "Disk quota exceeded", PFAD), VOLL),
        (UnidentifiedImageError(f"cannot identify image file {PFAD!r}"), UNLESBAR),
        (BildFehler("„x.jpg“ hat 9000×9000 Pixel – das ist zu groß."), KAPUTT),
        (Image.DecompressionBombError("Image size exceeds limit"), KAPUTT),
        (OSError("image file is truncated (5 bytes not processed)"), KAPUTT),
        (SyntaxError("broken PNG file"), KAPUTT),
        (MemoryError(), KAPUTT),
        (FileNotFoundError(errno.ENOENT, "No such file or directory", PFAD), UNBEKANNT),
        (RuntimeError(PFAD), UNBEKANNT),
    ):
        assert fehlerart(exc) == art, (exc, fehlerart(exc))
        assert "/" not in fehlerart(exc)
    print("Fehlerart je Art bestanden.")


def test_import_nennt_die_art():
    from app import wiki_import
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        t = aufbau(tmp)
        ziel = seite(t.adm, "Ziel Platzhalter")
        log = mitschreiben(t.app)
        # Echt: kein Bild, abgeschnitten, zu viele Pixel.
        r = importieren(t.adm, zip_aus([("k.md", "# K\n\n![k](k.jpg)\n![h](h.jpg)\n"), ("k.jpg", b"kein bild"),
                                        ("h.jpg", jpeg_halb())]), ziel["id"])
        text = hinweise(r)
        assert f"„k.jpg“ ließ sich nicht verarbeiten ({UNLESBAR}) – nicht übernommen." in text, text
        assert f"„h.jpg“ ließ sich nicht verarbeiten ({KAPUTT}) – nicht übernommen." in text, text
        from app import images
        alt = images.MAX_PIXEL
        images.MAX_PIXEL = 100
        try:
            r = importieren(t.adm, zip_aus([("g.md", "# G\n\n![g](g.png)\n"), ("g.png", png())]), ziel["id"])
        finally:
            images.MAX_PIXEL = alt
        assert f"„g.png“ ließ sich nicht verarbeiten ({KAPUTT}) – nicht übernommen." in hinweise(r)
        # Echt: Ablageordner schreibgeschützt (der Fall vom Server, wenn das Volumen einem anderen Nutzer gehört).
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            os.chmod(t.media, 0o500)
            try:
                r = importieren(t.adm, zip_aus([("s.md", "# S\n\n![s](s.png)\n"), ("s.png", png())]), ziel["id"])
            finally:
                os.chmod(t.media, 0o700)
            assert f"„s.png“ ließ sich nicht verarbeiten ({SCHREIBRECHTE}) – nicht übernommen." in hinweise(r)
        # Nachgestellt: Speicher voll und Unbekanntes – mit Serverpfad im Text der Ausnahme, der nicht nach außen geht.
        echt = wiki_import.store_wiki_file
        for exc, art in ((OSError(errno.ENOSPC, "No space left on device", PFAD), VOLL), (RuntimeError(PFAD), UNBEKANNT)):
            def kaputt(*_a, _exc=exc, **_k):
                raise _exc
            wiki_import.store_wiki_file = kaputt
            try:
                r = importieren(t.adm, zip_aus([("v.md", "# V\n\n![v](v.png)\n"), ("v.png", png())]), ziel["id"])
            finally:
                wiki_import.store_wiki_file = echt
            text = hinweise(r)
            assert f"„v.png“ ließ sich nicht verarbeiten ({art}) – nicht übernommen." in text, text
            assert "/data" not in text and PFAD not in str(r.json)
        # Das Protokoll behält den ganzen Fehler samt Traceback.
        fehler = [e for e in log.eintraege if "ließ sich nicht ablegen" in e.getMessage()]
        assert len(fehler) >= 5 and all(e.exc_info for e in fehler)
        assert any(PFAD in repr(e.exc_info[1]) for e in fehler)
    print("Import nennt die Art bestanden.")


def test_editor_nennt_die_art():
    from app import api_wiki
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        t = aufbau(tmp)
        log = mitschreiben(t.app)

        def hoch(name, daten):
            return t.adm.post("/api/wiki/files", data={"file": (io.BytesIO(daten), name)}, headers=H,
                              content_type="multipart/form-data")
        # Echt: kein Bild und abgeschnitten.
        r = hoch("kein.jpg", b"kein bild")
        assert r.status_code == 400 and r.json["error"] == f"Die Datei konnte nicht verarbeitet werden ({UNLESBAR}).", r.json
        r = hoch("halb.jpg", jpeg_halb())
        assert r.status_code == 400 and r.json["error"] == f"Die Datei konnte nicht verarbeitet werden ({KAPUTT}).", r.json
        # Echt: Ablageordner schreibgeschützt.
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            os.makedirs(t.media, exist_ok=True)
            os.chmod(t.media, 0o500)
            try:
                r = hoch("bild.png", png())
            finally:
                os.chmod(t.media, 0o700)
            assert r.json["error"] == f"Die Datei konnte nicht verarbeitet werden ({SCHREIBRECHTE}).", r.json
        # Nachgestellt: Speicher voll und Unbekanntes – auch beim Drehen und Zuschneiden.
        gut = hoch("gut.png", png())
        assert gut.status_code == 200, gut.json
        echt = (api_wiki.store_wiki_file, api_wiki.rotate_wiki_image, api_wiki.crop_wiki_image)
        for exc, art in ((OSError(errno.ENOSPC, "No space left on device", PFAD), VOLL),
                         (PermissionError(errno.EACCES, "Permission denied", PFAD), SCHREIBRECHTE),
                         (RuntimeError(PFAD), UNBEKANNT)):
            def kaputt(*_a, _exc=exc, **_k):
                raise _exc
            api_wiki.store_wiki_file = api_wiki.rotate_wiki_image = api_wiki.crop_wiki_image = kaputt
            try:
                r1 = hoch("x.png", png())
                r2 = t.adm.post("/api/wiki/files/drehung", headers=H, json={"file": gut.json["url"], "grad": 90})
                r3 = t.adm.post("/api/wiki/files/zuschnitt", headers=H,
                                json={"file": gut.json["url"], "x": 0, "y": 0, "w": 0.5, "h": 0.5})
            finally:
                api_wiki.store_wiki_file, api_wiki.rotate_wiki_image, api_wiki.crop_wiki_image = echt
            assert r1.status_code == 400 and r1.json["error"] == f"Die Datei konnte nicht verarbeitet werden ({art}).", r1.json
            assert r2.status_code == 400 and r2.json["error"] == f"Das Bild ließ sich nicht drehen ({art}).", r2.json
            assert r3.status_code == 400 and r3.json["error"] == f"Das Bild ließ sich nicht zuschneiden ({art}).", r3.json
            assert all(PFAD not in str(r.json) for r in (r1, r2, r3))
        assert sum(1 for e in log.eintraege if e.exc_info) >= 11
    print("Editor nennt die Art bestanden.")


if __name__ == "__main__":
    test_fehlerart_je_art()
    test_import_nennt_die_art()
    test_editor_nennt_die_art()
