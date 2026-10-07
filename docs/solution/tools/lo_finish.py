"""Доводка DOCX в LibreOffice (запускается внутри образа fsp-docs-render, нужен python3-uno).

    python3 lo_finish.py <вход.docx> <выход.docx> <выход.pdf>

Что делает: шрифты и цвета брендбука ФСП в стилях, A4 и поля, номера страниц внизу,
рамки и шапка таблиц, обновляет оглавление (поле TOC из pandoc), встраивает шрифты в DOCX,
сохраняет DOCX и экспортирует PDF с закладками.
"""

import contextlib
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.table import BorderLine2

BRAND = 0x402FFF  # основной цвет ФСП
TEXT = 0x1B1C21
LINE = 0xC8C9CA
FILL = 0xEDEDED
BODY_FONT = "Inter"
MONO_FONT = "JetBrains Mono"
PIPE = "fspdocs"


def prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def connect():
    office = subprocess.Popen(
        [
            "soffice",
            "--headless",
            "--invisible",
            "--nologo",
            "--norestore",
            f"--accept=pipe,name={PIPE};urp;StarOffice.ComponentContext",
        ]
    )
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local
    )
    for _ in range(90):
        try:
            ctx = resolver.resolve(f"uno:pipe,name={PIPE};urp;StarOffice.ComponentContext")
            return office, ctx
        except Exception:
            time.sleep(1)
    office.kill()
    sys.exit("LibreOffice не запустился")


def set_props(obj, **values):
    info = obj.getPropertySetInfo()
    for key, value in values.items():
        if info.hasPropertyByName(key):
            obj.setPropertyValue(key, value)


def style_paragraphs(doc):
    paras = doc.getStyleFamilies().getByName("ParagraphStyles")
    chars = doc.getStyleFamilies().getByName("CharacterStyles")

    def para(name, **values):
        if paras.hasByName(name):
            set_props(paras.getByName(name), **values)

    for name in paras.getElementNames():
        st = paras.getByName(name)
        set_props(
            st,
            CharFontName=BODY_FONT,
            CharFontNameAsian=BODY_FONT,
            CharFontNameComplex=BODY_FONT,
        )
    para("Standard", CharHeight=10.0, CharColor=TEXT)
    for name in ("Body Text", "First Paragraph", "Text Body"):
        para(name, CharHeight=10.0, ParaBottomMargin=160, ParaTopMargin=100)
    para("Compact", CharHeight=8.5, ParaBottomMargin=40, ParaTopMargin=40)
    for level, size in ((1, 18.0), (2, 13.5), (3, 11.5), (4, 10.5)):
        for name in (f"Heading {level}", f"heading {level}"):
            para(
                name,
                CharFontName=MONO_FONT,
                CharHeight=size,
                CharWeight=150.0,
                CharColor=BRAND if level <= 2 else TEXT,
                ParaTopMargin=420 if level == 1 else 300,
                ParaBottomMargin=160,
                ParaKeepTogether=True,
            )
    para(
        "Source Code",
        CharFontName=MONO_FONT,
        CharHeight=8.0,
        ParaBackColor=0xF4F4F6,
        ParaLeftMargin=150,
        ParaRightMargin=150,
    )
    para("Image Caption", CharHeight=8.5, CharColor=0x5A5B63, CharPosture=2)
    para("Captioned Figure", ParaAdjust=3)
    para("Figure", ParaAdjust=3)
    para("Contents Heading", CharFontName=MONO_FONT, CharHeight=18.0, CharColor=BRAND)
    for level in range(1, 4):
        para(f"Contents {level}", CharHeight=10.0 if level == 1 else 9.5)
    # титульный лист (custom-style из build_docs.py)
    para("FSP Title", CharFontName=MONO_FONT, CharHeight=34.0, CharWeight=150.0, CharColor=BRAND)
    para("FSP Subtitle", CharHeight=16.0, CharColor=TEXT, ParaBottomMargin=400)
    para("FSP Kind", CharFontName=MONO_FONT, CharHeight=12.0, CharColor=BRAND)
    para("FSP Meta", CharHeight=11.0, CharColor=TEXT, ParaBottomMargin=120)
    para("FSP Note", CharHeight=9.0, CharColor=0x5A5B63)
    for name in ("Verbatim Char", "VerbatimChar", "Source Text"):
        if chars.hasByName(name):
            set_props(chars.getByName(name), CharFontName=MONO_FONT, CharHeight=8.5)
    for name in ("Hyperlink", "Internet Link", "Internet link"):
        if chars.hasByName(name):
            set_props(chars.getByName(name), CharColor=BRAND)


def style_pages(doc):
    pages = doc.getStyleFamilies().getByName("PageStyles")
    for name in pages.getElementNames():
        st = pages.getByName(name)
        set_props(
            st,
            Width=21000,
            Height=29700,
            IsLandscape=False,
            LeftMargin=2000,
            RightMargin=1500,
            TopMargin=1700,
            BottomMargin=1500,
        )
        set_props(st, FooterIsOn=True)
        footer = st.getPropertyValue("FooterText") if st.getPropertyValue("FooterIsOn") else None
        if footer is not None:
            footer.setString("")
            cursor = footer.createTextCursor()
            set_props(cursor, ParaAdjust=1, CharHeight=8.0, CharColor=0x5A5B63)  # 1 = справа
            footer.insertString(cursor, "fsp-talent · сопроводительная документация · ", False)
            field = doc.createInstance("com.sun.star.text.TextField.PageNumber")
            field.NumberingType = 4  # арабские
            field.SubType = uno.Enum("com.sun.star.text.PageNumberType", "CURRENT")
            footer.insertTextContent(cursor, field, False)


def line(width=18, color=LINE):
    b = BorderLine2()
    b.Color = color
    b.LineWidth = width
    b.OuterLineWidth = width
    return b


def style_tables(doc):
    tables = doc.getTextTables()
    for i in range(tables.getCount()):
        table = tables.getByIndex(i)
        set_props(table, RepeatHeadline=True, HeaderRowCount=1, Split=True)
        for name in table.getCellNames():
            cell = table.getCellByName(name)
            for side in ("TopBorder", "BottomBorder", "LeftBorder", "RightBorder"):
                cell.setPropertyValue(side, line())
            set_props(cell, LeftBorderDistance=80, RightBorderDistance=80)
            header = name.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") == "1"
            if header:
                cell.setPropertyValue("BackColor", FILL)
            style_cell_text(cell, header)


VERBATIM = {"Verbatim Char", "VerbatimChar", "Source Text"}


def style_cell_text(cell, header):
    """Текст ячейки: Inter 8,5 pt, код — JetBrains Mono (стили таблиц из DOCX дают засечки)."""
    paragraphs = cell.getText().createEnumeration()
    while paragraphs.hasMoreElements():
        paragraph = paragraphs.nextElement()
        if not paragraph.supportsService("com.sun.star.text.Paragraph"):
            continue
        set_props(paragraph, ParaTopMargin=30, ParaBottomMargin=30)
        portions = paragraph.createEnumeration()
        while portions.hasMoreElements():
            portion = portions.nextElement()
            mono = portion.getPropertyValue("CharStyleName") in VERBATIM
            set_props(
                portion,
                CharFontName=MONO_FONT if mono else BODY_FONT,
                CharHeight=8.0 if mono else 8.5,
            )
            if header:
                set_props(portion, CharWeight=150.0)


def main():
    src, out_docx, out_pdf = (os.path.abspath(a) for a in sys.argv[1:4])
    office, ctx = connect()
    try:
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(src), "_blank", 0, (prop("Hidden", True),)
        )
        style_paragraphs(doc)
        style_pages(doc)
        style_tables(doc)
        indexes = doc.getDocumentIndexes()
        print(f"оглавлений: {indexes.getCount()}, таблиц: {doc.getTextTables().getCount()}")
        for _ in range(2):  # второй проход — номера страниц после разметки оглавления
            for i in range(indexes.getCount()):
                indexes.getByIndex(i).update()
        settings = doc.createInstance("com.sun.star.document.Settings")
        set_props(settings, EmbedFonts=True, EmbedOnlyUsedFonts=True)
        doc.storeToURL(uno.systemPathToFileUrl(out_docx), (prop("FilterName", "MS Word 2007 XML"),))
        pdf_options = uno.Any(
            "[]com.sun.star.beans.PropertyValue",
            (
                prop("ExportBookmarks", True),
                prop("UseTaggedPDF", True),
                prop("EmbedStandardFonts", True),
            ),
        )
        filter_data = PropertyValue("FilterData", 0, pdf_options, 0)
        args = uno.Any(
            "[]com.sun.star.beans.PropertyValue",
            (prop("FilterName", "writer_pdf_Export"), filter_data),
        )
        uno.invoke(doc, "storeToURL", (uno.systemPathToFileUrl(out_pdf), args))
        doc.close(True)
    finally:
        with contextlib.suppress(Exception):
            desktop.terminate()
        office.wait(timeout=30)
    print(f"записано: {out_docx}, {out_pdf}")


if __name__ == "__main__":
    main()
