"""Prüfsummen-Stempel für festgeschriebene Protokolle (Konzept „PDF-Prüfprotokoll“).

1. WeasyPrint erzeugt das Protokoll vollständig; angehängte PDFs kommen per inkrementellem Update dazu.
   Über diese N Bytes geht SHA-256.
2. Ein zweites inkrementelles Update hängt nur den Stempel an: im Fuß jeder Seite
   „SHA-256 (erste N Bytes): <hex>“ und der Hinweis auf die Prüfseite. Die ersten N Bytes bleiben Byte
   für Byte, wie sie waren – nachrechenbar mit `head -c N datei.pdf | sha256sum`.

Den Stempel selbst kann die Summe nicht abdecken (keine Datei enthält ihre eigene Gesamtprüfsumme); dafür
steht die Summe der ganzen Datei in der Datenbank, und die Prüfseite vergleicht beides.

Der Stempel ist ein einziges Form-XObject, auf das jede Seite nur verweist; die Seiteninhalte selbst
bleiben unangetastet (eingerahmt in q … Q, damit ein offener Grafikzustand der Seite den Stempel nicht
verschiebt). Ein Zusammenführen der Seiten mit pypdf (merge_page) hätte dagegen die von WeasyPrint
geteilte Farbraumtabelle bei jeder Seite um eine umbenannte Kopie erweitert – rund 5 KB je Seite."""
import hashlib
import io
import re
import struct

from pypdf import PdfReader, PdfWriter
from pypdf.constants import TrailerKeys as TK
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, IndirectObject,
                           NameObject, NumberObject, StreamObject)

STEMPEL_TEXT = "SHA-256 (erste {n} Bytes): {sha}"
# Kennung als PDF-Kommentar am Anfang des Stempel-Nachtrags: unkomprimiert lesbar, auch wenn eine veränderte
# Datei sich nicht mehr als PDF öffnen lässt – so ordnet die Prüfseite sie trotzdem ihrem Protokoll zu.
KENNUNG = "%Stroemis-Protokoll {pid} N={n} SHA-256={sha}"
KENNUNG_MUSTER = re.compile(rb"%Stroemis-Protokoll ([A-Z]-\d{4}-\d{6,}(?:-\d+)?) N=(\d+) SHA-256=([0-9a-f]{64})")
XOBJEKT_NAME = "/StroemisStempel"
A4_BREITE = 595.276                  # Breite der Stempelvorlage (DIN A4 hochkant) in Punkt
STREIFEN = 14 * 72 / 25.4            # unten so viel Platz (14 mm) braucht der Stempel


class _Nachtrag(PdfWriter):
    """pypdf im inkrementellen Modus, mit zwei Korrekturen am angehängten Querverweis-Strom (pypdf 6.19):
    pypdf führt den Strom nicht in seinem eigenen /Index (qpdf: „xref entry for the xref stream itself is
    missing“) und schreibt nach „obj“ keinen Zeilenumbruch (PDF/A, ISO 19005 6.1.9). Außerdem übernimmt der
    neue Trailer /Info aus dem alten – ein Nachtrag soll alle Einträge des vorigen Trailers fortführen.
    Der Rest entspricht PdfWriter._write_increment."""

    kennung = None

    def _write_increment(self, stream):
        self._reader.stream.seek(-1, io.SEEK_END)
        if self._reader.stream.read(1) not in (b"\n", b"\r"):
            stream.write(b"\n")          # sonst klebte das erste neue Objekt am %%EOF der Vorlage
        if self.kennung:
            stream.write(self.kennung.encode("ascii") + b"\n")
        positionen = {}
        n_alt = len(self._original_hash)
        for i, obj in enumerate(self._objects):
            if obj is not None and (i >= n_alt or obj.hash_bin() != self._original_hash[i]):
                positionen[i + 1] = stream.tell()
                stream.write(f"{i + 1} 0 obj\n".encode())
                obj.write_to_stream(stream)
                stream.write(b"\nendobj\n")
        xref_pos = stream.tell()
        xr_id = len(self._objects) + 1
        positionen[xr_id] = xref_pos
        bloecke = []
        for idnum in sorted(positionen):
            if bloecke and bloecke[-1][0] + bloecke[-1][1] == idnum:
                bloecke[-1][1] += 1
            else:
                bloecke.append([idnum, 1])
        d = {
            NameObject("/Type"): NameObject("/XRef"),
            NameObject("/Size"): NumberObject(xr_id + 1),
            NameObject("/Root"): self.root_object.indirect_reference,
            NameObject("/Filter"): NameObject("/FlateDecode"),
            NameObject("/Index"): ArrayObject([NumberObject(x) for b in bloecke for x in b]),
            NameObject("/W"): ArrayObject([NumberObject(1), NumberObject(4), NumberObject(1)]),
            NameObject(TK.PREV): NumberObject(self._reader._startxref),
            "__streamdata__": b"",
        }
        info = self._reader.trailer.raw_get(TK.INFO) if TK.INFO in self._reader.trailer else None
        if isinstance(info, IndirectObject):
            d[NameObject(TK.INFO)] = info
        if self._ID:
            d[NameObject(TK.ID)] = self._ID
        xr = StreamObject.initialize_from_dictionary(d)
        xr.set_data(b"".join(struct.pack(">BIB", 1, positionen[k], 0) for k in sorted(positionen)))
        stream.write(f"{xr_id} 0 obj\n".encode())
        xr.write_to_stream(stream)
        stream.write(f"\nendobj\nstartxref\n{xref_pos}\n%%EOF\n".encode())


def sha256(daten):
    return hashlib.sha256(daten).hexdigest()


def stempel_text(n, sha):
    return STEMPEL_TEXT.format(n=n, sha=sha)


def _schreiben(schreiber, basis):
    puffer = io.BytesIO()
    schreiber.write(puffer)
    neu = puffer.getvalue()
    if neu[:len(basis)] != basis:                    # das Verfahren steht und fällt damit
        raise RuntimeError("Das inkrementelle Update hat den Dateianfang verändert.")
    return neu


def _leser(daten):
    leser = PdfReader(io.BytesIO(daten))
    if leser.is_encrypted:
        leser.decrypt("")               # Anhänge mit leerem Kennwort lassen sich so anfügen (anhang._pdf_lesen)
    return leser


# Aktionen, die beim Öffnen oder Anklicken etwas ausführen oder Daten wegschicken. Verweise (URI, GoTo) bleiben.
_AKTIVE_AKTIONEN = {"/JavaScript", "/Launch", "/SubmitForm", "/ImportData", "/ResetForm", "/Rendition", "/Sound",
                    "/Movie", "/RichMediaExecute", "/GoToE", "/GoToR", "/Hide", "/SetOCGState", "/Trans", "/GoTo3DView"}


def _entschaerfen(seite):
    """Aktive Teile einer angefügten Seite entfernen: Seitenaktionen (/AA), Aktionen von Anmerkungen, die etwas
    ausführen, und deren Zusatzaktionen. Was die Seite zeigt – auch ausgefüllte Formularfelder (ihr
    Erscheinungsbild) und Verweise –, bleibt."""
    if "/AA" in seite:
        del seite["/AA"]
    anmerkungen = seite.get("/Annots")
    anmerkungen = anmerkungen.get_object() if anmerkungen is not None else []
    for ref in anmerkungen:
        anm = ref.get_object()
        if not isinstance(anm, DictionaryObject):
            continue
        if "/AA" in anm:
            del anm["/AA"]
        aktion = anm.get("/A")
        aktion = aktion.get_object() if aktion is not None else None
        if isinstance(aktion, DictionaryObject) and (aktion.get("/S") in _AKTIVE_AKTIONEN or "/Next" in aktion):
            del anm["/A"]


def anhaengen(basis, anhaenge):
    """Die Seiten der angehängten PDFs (Liste von bytes) hinten an das Protokoll – als inkrementelles
    Update, das Protokoll selbst bleibt am Dateianfang unverändert. Angefügt wird nur, was man sieht:
    Skripte, ausführende Aktionen und das Formular-Wörterbuch eines Anhangs kommen nicht ins Protokoll – es wird
    im Browser angezeigt und soll beim Öffnen nichts ausführen."""
    if not anhaenge:
        return basis
    schreiber = _Nachtrag(io.BytesIO(basis), incremental=True)
    for daten in anhaenge:
        leser = _leser(daten)
        # Vor dem Anfügen entschärfen (nur im Speicher): Was keine Seite mehr erreicht, kopiert pypdf gar nicht erst.
        for seite in leser.pages:
            _entschaerfen(seite)
        if "/AcroForm" in leser.root_object:
            del leser.root_object["/AcroForm"]
        schreiber.append(leser, import_outline=False)
    return _schreiben(schreiber, basis)


def _box(seite):
    box = seite.cropbox
    return float(box.left), float(box.bottom), float(box.right), float(box.top)


def _matrix(seite):
    """Abbildung der Stempelvorlage (A4 hochkant, Stempel unten links) auf den sichtbaren unteren Rand der
    Seite – auch bei gedrehten Seiten (/Rotate) und anderen Formaten; schmalere Seiten verkleinern ihn."""
    x0, y0, x1, y1 = _box(seite)
    drehung = (seite.rotation or 0) % 360
    breite = (y1 - y0) if drehung in (90, 270) else (x1 - x0)
    s = min(1.0, breite / A4_BREITE) if breite > 0 else 1.0
    a, b, c, d, e, f = {0: (1, 0, 0, 1, x0, y0), 90: (0, 1, -1, 0, x1, y0),
                        180: (-1, 0, 0, -1, x1, y1), 270: (0, -1, 1, 0, x0, y1)}.get(drehung, (1, 0, 0, 1, x0, y0))
    return (a * s, b * s, c * s, d * s, e, f)


def _streifen_anfuegen(seite):
    """Eine angefügte Seite (Scan, fremdes PDF) hat keinen freien Rand für den Stempel: Sie bekommt am sichtbaren
    unteren Rand einen Streifen von 14 mm und – ist sie schmaler – die Breite von DIN A4. So verdeckt der Stempel
    nichts vom Anhang und wird auf kleinen Fotoseiten nicht unlesbar klein. Geändert werden nur die Seitengrenzen
    (im Nachtrag), nicht der Inhalt."""
    x0, y0, x1, y1 = _box(seite)
    drehung = (seite.rotation or 0) % 360
    if drehung == 90:
        x1 += STREIFEN
        y1 = max(y1, y0 + A4_BREITE)
    elif drehung == 180:
        y1 += STREIFEN
        x0 = min(x0, x1 - A4_BREITE)
    elif drehung == 270:
        x0 -= STREIFEN
        y0 = min(y0, y1 - A4_BREITE)
    else:
        y0 -= STREIFEN
        x1 = max(x1, x0 + A4_BREITE)
    m = seite.mediabox
    seite[NameObject("/MediaBox")] = ArrayObject([FloatObject(v) for v in (
        min(x0, float(m.left)), min(y0, float(m.bottom)), max(x1, float(m.right)), max(y1, float(m.top)))])
    seite[NameObject("/CropBox")] = ArrayObject([FloatObject(v) for v in (x0, y0, x1, y1)])


def _zahl(x):
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def _strom(schreiber, daten):
    s = DecodedStreamObject()
    s.set_data(daten)
    return schreiber._add_object(s.flate_encode())


def stempeln(basis, vorlage_pdf, protokoll_id=None, eigene_seiten=None):
    """Den Stempel (erste Seite von vorlage_pdf, DIN A4) auf jede Seite von basis legen. Liefert die fertige
    Datei; ihre ersten len(basis) Bytes sind basis. eigene_seiten: so viele Seiten am Anfang hat WeasyPrint gesetzt
    (mit freiem Rand unten); die übrigen sind angefügte Anhänge und bekommen einen Streifen dazu."""
    vorlage = PdfReader(io.BytesIO(vorlage_pdf)).pages[0]
    schreiber = _Nachtrag(io.BytesIO(basis), incremental=True)
    if protokoll_id:
        schreiber.kennung = KENNUNG.format(pid=protokoll_id, n=len(basis), sha=sha256(basis))

    inhalt = vorlage.get_contents()      # ein Strom ohne Wörterbucheinträge ist „falsy“ – daher „is None“
    form = DecodedStreamObject()
    form.set_data(inhalt.get_data() if inhalt is not None else b"")
    form.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"): ArrayObject([FloatObject(v) for v in vorlage.mediabox]),
        NameObject("/Resources"): vorlage["/Resources"].clone(schreiber),
    })
    form_ref = schreiber._add_object(form.flate_encode())
    auf = _strom(schreiber, b"q\n")
    zu = {}
    # Eigener Name je Protokoll: Ein angehängtes, schon gestempeltes Protokoll trägt seinen eigenen Stempel unter
    # /StroemisStempel… – den darf der neue nicht ersetzen.
    eigener_name = f"{XOBJEKT_NAME}{sha256(basis)[:12]}"

    for nr, seite in enumerate(schreiber.pages):
        if eigene_seiten is not None and nr >= eigene_seiten:
            _streifen_anfuegen(seite)
        m = _matrix(seite)
        res_alt = seite.get(NameObject("/Resources"))
        res_alt = res_alt.get_object() if res_alt is not None else DictionaryObject()
        xo_alt = res_alt.get(NameObject("/XObject"))
        xo_alt = xo_alt.get_object() if xo_alt is not None else DictionaryObject()
        name = eigener_name
        while NameObject(name) in xo_alt:
            name += "x"
        if (m, name) not in zu:
            zu[(m, name)] = _strom(schreiber, ("Q\nq " + " ".join(_zahl(v) for v in m) + f" cm {name} Do Q\n").encode())
        alt = seite.get(NameObject("/Contents"))
        inhalt = ArrayObject([auf])
        if isinstance(alt, IndirectObject) and isinstance(alt.get_object(), ArrayObject):
            inhalt.extend(alt.get_object())
        elif isinstance(alt, ArrayObject):
            inhalt.extend(alt)
        elif alt is not None:
            inhalt.append(alt)
        inhalt.append(zu[(m, name)])
        # Eigene, flache Kopie der Ressourcen: Geteilte Unterwörterbücher (Schriften, Farbräume) bleiben
        # unverändert, nur /XObject bekommt den Stempel dazu.
        res = DictionaryObject({NameObject(k): v for k, v in res_alt.items()})
        xo = DictionaryObject({NameObject(k): v for k, v in xo_alt.items()})
        xo[NameObject(name)] = form_ref
        res[NameObject("/XObject")] = xo
        seite[NameObject("/Resources")] = res
        seite[NameObject("/Contents")] = inhalt
    return _schreiben(schreiber, basis)


def kennung_lesen(daten):
    """(Protokoll-ID, N, Summe) aus dem Kommentar des Stempel-Nachtrags oder None."""
    treffer = list(KENNUNG_MUSTER.finditer(daten))
    if not treffer:
        return None
    m = treffer[-1]
    return m.group(1).decode(), int(m.group(2)), m.group(3).decode()
