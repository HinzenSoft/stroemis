"""PDF-Protokolle des Moduls Material: Prüf-, Aussonderungs- und Sammelprotokoll, dazu die Vorlage des
Prüfsummen-Stempels (Konzept „PDF-Prüfprotokoll“) – und der Lebenslauf eines Artikels (lebenslauf.py), der auf
Abruf entsteht und nicht festgeschrieben wird.

WeasyPrint setzt die Jinja-Vorlagen unter templates/material/pdf/ als PDF/A-3b. Die Vorlagen bekommen alle
Werte fertig formatiert (Datum, Ordnerpfad, Ergebnistext) und rechnen nichts mehr um; dieses Modul liefert
nur die Bausteine, die Bytes brauchen – Fotos und Unterschrift als data:-URI, den QR-Code als SVG.

Nachgeladen wird beim Setzen nichts: Bilder stecken als data:-URI im HTML, und außer den Hausschriften
unter static/fonts darf WeasyPrint keine Datei und keine Adresse öffnen (_Abholer). So kann ein Wert aus
der Datenbank nie dazu führen, dass der Server beim Setzen eine fremde Adresse abruft oder eine Datei des
Servers ins Protokoll zieht.

Gesetzt wird mit der Jinja-Umgebung der App, aber ohne deren Kontextprozessoren: Die brauchen eine
Anfrage (angemeldeter Nutzer), ein Protokoll entsteht aber auch ohne – im Beispielbestand-Skript, beim Abschluss eines
Durchgangs. Vor dem Setzen läuft jeder Text durch _sauber(): Zeichen, die keine der beiden Schriften hat,
würden als leeres Kästchen (.notdef) gesetzt und machten die Datei zu einem ungültigen PDF/A.

Unten auf jeder Seite eines Protokolls bleiben 14 mm frei: Dort legt services/stempel.py nach dem Festschreiben
den Stempel aus stempelvorlage() hin. Der Lebenslauf bekommt keinen Stempel und braucht den Platz nicht."""
import base64
import io
import logging
import os
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from flask import current_app

PDF_VARIANTE = "pdf/a-3b"
VORLAGEN = ("pruefprotokoll", "aussonderungsprotokoll", "sammelprotokoll", "lebenslauf", "bericht")
SCHRIFT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                            "static", "fonts"))
JPEG_QUALITAET = 85
# So viele Zeichen fasst eine Zeile des Stempels (DejaVu Sans Mono 6,5 pt auf 180 mm); eine längere bricht
# um, und der Kasten ragt über die freien 14 mm hinaus.
STEMPEL_ZEICHEN = 128
# Die Hausschriften liegen als WOFF2 vor. WeasyPrint entpackt sie sonst bei jedem Protokoll neu (fontTools,
# rund 0,15 s); entpackt einmal je Prozess und als TrueType gereicht, bleibt es bei einem Mal.
_SCHRIFTEN = {}
_ZEICHEN = None                   # Zeichenvorrat der Schriften, siehe _zeichenvorrat()
_SCHRIFTSATZ = None               # Klasse, siehe _schriftsatz()

log = logging.getLogger(__name__)
# WeasyPrint meldet jeden Arbeitsschritt und jede Seite auf INFO (beim Sammelprotokoll mit 500 Zeilen rund
# 45 Zeilen je Protokoll), fontTools jedes Entpacken einer Schrift – im Protokoll der App sagt das nichts.
logging.getLogger("weasyprint.progress").setLevel(logging.WARNING)
logging.getLogger("fontTools.ttLib.woff2").setLevel(logging.WARNING)

# Fontconfig fettet einen Schnitt künstlich, wenn der fette Schnitt ein Zeichen nicht hat (90-synthetic.conf
# der Systemkonfiguration), und gibt ihn dabei als fett aus. DLRG Univers Bold fehlen etwa Ł, μ und −, die der
# Normalschnitt hat. WeasyPrint unterscheidet Schriften nur nach Familie, Stärke und Lage: Der künstlich
# gefettete Normalschnitt fiele mit dem echten fetten Schnitt zusammen, das PDF bekäme die Glyphennummern des
# einen mit der Schriftdatei des anderen – falsche Zeichen („ˇukasz“ statt „Łukasz“) und kein gültiges PDF/A.
# Die erste Regel läuft nach der Systemkonfiguration und nimmt das zurück: Das Zeichen kommt ungefettet aus dem
# Normalschnitt, unter dessen eigenem Namen.
# Die übrigen drei betreffen Emoji: Pango verlangt dafür die Familie „emoji“, die Sprache „und-zsye“ oder eine
# farbige Schrift, und das führt – wo installiert – zu einer Bitmap-Schrift (Noto Color Emoji), die PDF/A nicht
# zulässt. Emoji kommen deshalb immer aus DejaVu Sans, wie im Docker-Image ohnehin.
_SCHRIFTREGELN = b"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <match target="font">
    <test name="embolden"><bool>true</bool></test>
    <edit name="embolden" mode="assign"><bool>false</bool></edit>
    <edit name="weight" mode="assign"><const>regular</const></edit>
  </match>
  <match target="pattern">
    <test name="family"><string>emoji</string></test>
    <edit name="family" mode="assign_replace"><string>DejaVu Sans</string></edit>
  </match>
  <match target="pattern">
    <test name="lang"><string>und-zsye</string></test>
    <edit name="lang" mode="delete"/>
  </match>
  <match target="pattern">
    <test name="color"><bool>true</bool></test>
    <edit name="color" mode="assign"><bool>false</bool></edit>
  </match>
</fontconfig>"""

# Zeilenwechsel in anderer Schreibweise (Wagenrücklauf, NEL, Zeilen- und Absatztrenner) werden zu "\n";
# übrige Steuer- und Formatzeichen (Unicode Cc, Cf) fallen weg, ebenso Variantenwähler, die keine der Schriften
# führt. Das weiche Trennzeichen bleibt – es ist ein Trennhinweis, kein Zeichen.
_ZEILENWECHSEL = str.maketrans({"\r": "\n", "\u0085": "\n", "\u2028": "\n", "\u2029": "\n"})
_ASCII_STEUER = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_IMMER_ERLAUBT = frozenset("\n\t\u00ad")


def _schrift(pfad):
    daten = _SCHRIFTEN.get(pfad)
    if daten is None:
        with open(pfad, "rb") as fh:
            daten = fh.read()
        if daten[:4] == b"wOF2":
            from fontTools.ttLib import woff2
            puffer = io.BytesIO()
            woff2.decompress(io.BytesIO(daten), puffer)
            daten = puffer.getvalue()
        _SCHRIFTEN[pfad] = daten
    return daten


def _abholer():
    """URL-Abholer für WeasyPrint: nur data:-URIs und die Schriftdateien unter static/fonts. Erst hier
    gebaut, weil die Klasse von WeasyPrint erbt und dessen Import den App-Start nicht bremsen soll."""
    from weasyprint.urls import URLFetcher, URLFetcherResponse

    class _Abholer(URLFetcher):
        def fetch(self, url, headers=None):
            if url.startswith("data:"):
                return super().fetch(url, headers)
            teile = urlsplit(url)
            if teile.scheme == "file" and teile.netloc in ("", "localhost"):
                pfad = os.path.realpath(unquote(teile.path))
                wurzel = os.path.realpath(SCHRIFT_DIR)
                if os.path.commonpath([pfad, wurzel]) == wurzel and os.path.isfile(pfad):
                    return URLFetcherResponse(url, _schrift(pfad))
            raise ValueError(f"Beim Setzen des Protokolls nicht erlaubt: {url[:80]}")

    return _Abholer()


def _schriftsatz():
    """Schriftkonfiguration für ein Protokoll: die von WeasyPrint, dazu die _SCHRIFTREGELN. Die
    Klasse entsteht beim ersten Aufruf – sie erbt von WeasyPrint, dessen Import den App-Start nicht bremsen
    soll."""
    global _SCHRIFTSATZ
    if _SCHRIFTSATZ is None:
        from weasyprint.text.ffi import ffi, fontconfig, pangoft2
        from weasyprint.text.fonts import FontConfiguration

        class _Schriftsatz(FontConfiguration):
            def __init__(self):
                super().__init__()
                fontconfig.FcConfigParseAndLoadFromMemory(self._config, _SCHRIFTREGELN, True)
                pangoft2.pango_fc_font_map_config_changed(ffi.cast("PangoFcFontMap *", self.font_map))

        _SCHRIFTSATZ = _Schriftsatz
    return _SCHRIFTSATZ()


def _setzen(html):
    import weasyprint
    from weasyprint.urls import path2url
    # Die Vorlagen binden die Schriften relativ ein (url("dlrg-univers-regular.woff2")) – die Basisadresse
    # ist deshalb das Schriftverzeichnis selbst.
    dokument = weasyprint.HTML(string=html, base_url=path2url(SCHRIFT_DIR + os.sep), url_fetcher=_abholer())
    return dokument.write_pdf(pdf_variant=PDF_VARIANTE, font_config=_schriftsatz())


def _systemschrift(familie):
    """Datei der Systemschrift „familie“ laut Fontconfig, None wenn es sie nicht gibt."""
    from weasyprint.text.ffi import ffi, fontconfig
    config = fontconfig.FcInitLoadConfigAndFonts()
    try:
        muster = ffi.gc(fontconfig.FcPatternCreate(), fontconfig.FcPatternDestroy)
        fontconfig.FcPatternAddString(muster, b"family", familie.encode())
        fontconfig.FcConfigSubstitute(config, muster, fontconfig.FcMatchPattern)
        fontconfig.FcDefaultSubstitute(muster)
        treffer = fontconfig.FcFontMatch(config, muster, ffi.new("FcResult *"))
        if treffer == ffi.NULL:
            return None
        treffer = ffi.gc(treffer, fontconfig.FcPatternDestroy)
        wert = ffi.new("FcChar8 **")
        if (fontconfig.FcPatternGetString(treffer, b"family", 0, wert) != fontconfig.FcResultMatch
                or ffi.string(wert[0]).decode() != familie
                or fontconfig.FcPatternGetString(treffer, b"file", 0, wert) != fontconfig.FcResultMatch):
            return None
        return os.fsdecode(ffi.string(wert[0]))
    finally:
        fontconfig.FcConfigDestroy(config)


def _zeichenvorrat():
    """Alle Zeichen, die ein Protokoll sicher setzen kann: was DLRG Univers (Normalschnitt) oder die
    Ersatzschrift DejaVu Sans hat. Einmal je Prozess aus den Zeichentabellen der Schriften gelesen."""
    global _ZEICHEN
    if _ZEICHEN is None:
        from fontTools.ttLib import TTFont
        codes = set(TTFont(io.BytesIO(_schrift(os.path.join(SCHRIFT_DIR, "dlrg-univers-regular.woff2"))),
                           lazy=True).getBestCmap())
        try:
            pfad = _systemschrift("DejaVu Sans")
            if pfad:
                codes |= set(TTFont(pfad, lazy=True, fontNumber=0).getBestCmap())
        except Exception as exc:          # ohne Ersatzschrift bleibt der Vorrat von DLRG Univers
            log.warning("Zeichenvorrat von DejaVu Sans nicht lesbar: %s", exc)
        # Steuer- und Formatzeichen zählen nicht mit, auch wenn eine Zeichentabelle sie führt: DLRG Univers
        # bildet etwa U+0080 auf das Euro-Zeichen ab (alte Windows-Belegung), Pango setzt dafür aber .notdef.
        _ZEICHEN = frozenset(z for z in map(chr, codes)
                             if unicodedata.category(z) not in ("Cc", "Cf", "Zl", "Zp", "Cs")) | _IMMER_ERLAUBT
    return _ZEICHEN


def _sauber(text, vorrat):
    """Text so, dass jedes Zeichen eine Glyphe hat: Zeilenwechsel vereinheitlicht, Steuer- und
    Formatzeichen entfernt, alles, was keine der Schriften hat, als U+FFFD. Reiner ASCII-Text ohne
    Steuerzeichen – die meisten Werte und alle data:-URIs – kommt unverändert zurück."""
    if text.isascii() and not _ASCII_STEUER.search(text):
        return text
    text = text.replace("\r\n", "\n").translate(_ZEILENWECHSEL)
    fremd = set(text) - vorrat
    if not fremd:
        return text
    ersatz = {}
    for z in fremd:
        weg = (unicodedata.category(z) in ("Cc", "Cf") or "\ufe00" <= z <= "\ufe0f"
               or "\U000e0100" <= z <= "\U000e01ef" or z == "\u034f")
        ersatz[ord(z)] = None if weg else "\ufffd"
    return text.translate(ersatz)


def _bereinigt(wert, vorrat):
    """Die Daten eines Protokolls mit jedem Text durch _sauber(); alles andere bleibt, wie es ist."""
    if isinstance(wert, str):
        return _sauber(wert, vorrat)
    if isinstance(wert, dict):
        return {k: _bereinigt(v, vorrat) for k, v in wert.items()}
    if isinstance(wert, (list, tuple)):
        return [_bereinigt(v, vorrat) for v in wert]
    return wert


def _leer_statt_none(wert):
    return "" if wert is None else wert


def _vorlagen():
    """Jinja-Umgebung der Protokolle: die der App (Lader, Autoescape für .html, Filter), aber ohne deren
    Kontextprozessoren – die brauchen eine Anfrage – und mit None als leerem Text statt „None“. Einmal je
    App angelegt."""
    app = current_app._get_current_object()
    umgebung = app.extensions.get("material_pdf_jinja")
    if umgebung is None:
        umgebung = app.jinja_env.overlay(finalize=_leer_statt_none, cache_size=20)
        app.extensions["material_pdf_jinja"] = umgebung
    return umgebung


def rendern(vorlage, daten):
    """Ein Protokoll als PDF/A-3b (bytes). vorlage ist „pruefprotokoll“, „aussonderungsprotokoll“,
    „sammelprotokoll“, „lebenslauf“ oder „bericht“ (Jahresbericht je Zweig, bericht.py), daten das fertig formatierte
    dict dazu (dokument, artikel, pruefung, …). Braucht einen Flask-App-Kontext, keine Anfrage."""
    if vorlage not in VORLAGEN:
        raise ValueError(f"Unbekannte Protokollvorlage: {vorlage}")
    daten = _bereinigt(daten, _zeichenvorrat())
    return _setzen(_vorlagen().get_template(f"material/pdf/{vorlage}.html").render(**daten))


def stempelvorlage(zeilen):
    """Vorlage des Prüfsummen-Stempels: eine Seite DIN A4 hochkant, sonst durchsichtig, unten links ein
    weißer Kasten mit den Textzeilen (Liste von str) in DejaVu Sans Mono 6,5 pt. Zwei Zeilen bleiben
    innerhalb der unteren 14 mm, die jede Protokollseite dafür freihält; eine Zeile fasst bis
    STEMPEL_ZEICHEN Zeichen, eine längere bricht um und schiebt den Kasten darüber hinaus (das steht dann
    als Warnung im Protokoll der App). Liefert PDF-bytes (PDF/A-3b); services/stempel.py legt die Seite als
    Form-XObject auf jede Seite des Protokolls. Braucht einen Flask-App-Kontext."""
    vorrat = _zeichenvorrat()
    zeilen = [_sauber(str(z), vorrat) for z in zeilen]
    for z in zeilen:
        if len(z) > STEMPEL_ZEICHEN:
            log.warning("Stempelzeile mit %d Zeichen (höchstens %d) bricht um und ragt über den freien Rand: %s",
                        len(z), STEMPEL_ZEICHEN, z[:60])
    return _setzen(_vorlagen().get_template("material/pdf/stempel.html").render(zeilen=zeilen))


def bild_daten_uri(pfad, max_kante=1200):
    """Foto (JPEG, PNG, WebP) als data:-URI für das Protokoll: verkleinert auf höchstens max_kante Pixel
    an der langen Seite und immer als RGB-JPEG – ein CMYK-JPEG oder ein PNG mit Alpha passte nicht zu
    PDF/A mit sRGB-Ausgabeprofil. None, wenn die Datei fehlt oder kein lesbares Bild ist."""
    if not pfad or not os.path.isfile(pfad):
        return None
    from PIL import Image, ImageOps
    try:
        with Image.open(pfad) as roh:
            roh.draft("RGB", (max_kante, max_kante))      # JPEG gleich verkleinert dekodieren
            # Die web-Fassung ist schon gedreht und ohne EXIF gespeichert; bei einer Datei, die die
            # Drehung noch im EXIF trägt, stellt das hier die Ausrichtung her – sonst bleibt alles, wie es ist.
            bild = ImageOps.exif_transpose(roh)
            if bild.mode in ("RGBA", "LA", "PA") or (bild.mode == "P" and "transparency" in bild.info):
                bild = bild.convert("RGBA")
                grund = Image.new("RGB", bild.size, (255, 255, 255))
                grund.paste(bild, mask=bild.split()[-1])
                bild = grund
            elif bild.mode != "RGB":
                bild = bild.convert("RGB")
            if max(bild.size) > max_kante:
                bild.thumbnail((max_kante, max_kante), Image.Resampling.LANCZOS)
            puffer = io.BytesIO()
            bild.save(puffer, "JPEG", quality=JPEG_QUALITAET, optimize=True)
    except Exception:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(puffer.getvalue()).decode("ascii")


def png_daten_uri(png_bytes):
    """Unterschrift (PNG mit Alpha, so wie das Unterschriftenfeld sie speichert) als data:-URI; None bei
    leerem Wert."""
    if not png_bytes:
        return None
    return "data:image/png;base64," + base64.b64encode(bytes(png_bytes)).decode("ascii")


def qr_svg(url):
    """QR-Code als SVG-Text ohne XML-Deklaration, zum Einsetzen ins HTML. Fehlerkorrektur M und zwei
    Module Rand – den übrigen Freiraum hält das Layout. Die Größe setzt die Vorlage (nur viewBox). Für
    die Adresse am besten qr.adresse() nehmen: Den Hostnamen in Punycode öffnet jede Kamera-App."""
    import segno
    code = segno.make(url, error="m", micro=False, boost_error=False,
                      encoding=None if url.isascii() else "utf-8")
    return code.svg_inline(border=2, omitsize=True, dark="#000", svgclass="qr", lineclass=None)
