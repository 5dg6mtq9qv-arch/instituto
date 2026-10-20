#!/usr/bin/python3
"""Construye la plantilla ODT de matrícula con el diseño histórico del PDF.

Requiere una instancia de LibreOffice escuchando en el puerto indicado, por ejemplo:
soffice --headless --accept='socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext'
"""

import argparse
from pathlib import Path

import uno


BLUE = 0x16417A
RED = 0x803D47
PALE_BLUE = 0xE3EBF9
PAGE_WIDTH = 21000
PAGE_HEIGHT = 29700
REF_WIDTH = 1092
REF_HEIGHT = 1600


def point(x, y):
    value = uno.createUnoStruct("com.sun.star.awt.Point")
    value.X = int(x)
    value.Y = int(y)
    return value


def size(width, height):
    value = uno.createUnoStruct("com.sun.star.awt.Size")
    value.Width = int(width)
    value.Height = int(height)
    return value


def property_value(name, value):
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name = name
    prop.Value = value
    return prop


class TemplateBuilder:
    def __init__(self, document, graphic_provider):
        self.document = document
        self.graphic_provider = graphic_provider
        self.page = document.DrawPage
        self.no_fill = uno.Enum("com.sun.star.drawing.FillStyle", "NONE")
        self.solid_fill = uno.Enum("com.sun.star.drawing.FillStyle", "SOLID")
        self.no_line = uno.Enum("com.sun.star.drawing.LineStyle", "NONE")
        self.solid_line = uno.Enum("com.sun.star.drawing.LineStyle", "SOLID")
        self.at_page = uno.Enum("com.sun.star.text.TextContentAnchorType", "AT_PAGE")
        self.alignments = {
            "left": uno.Enum("com.sun.star.style.ParagraphAdjust", "LEFT"),
            "center": uno.Enum("com.sun.star.style.ParagraphAdjust", "CENTER"),
            "right": uno.Enum("com.sun.star.style.ParagraphAdjust", "RIGHT"),
        }
        self.vertical_top = uno.Enum("com.sun.star.drawing.TextVerticalAdjust", "TOP")
        self.vertical_center = uno.Enum("com.sun.star.drawing.TextVerticalAdjust", "CENTER")

    def x(self, value):
        return round(value * PAGE_WIDTH / REF_WIDTH)

    def y(self, value):
        return round(value * PAGE_HEIGHT / REF_HEIGHT)

    def add(self, shape, x, y, width, height):
        shape.Position = point(self.x(x), self.y(y))
        shape.Size = size(self.x(width), self.y(height))
        shape.AnchorType = self.at_page
        shape.AnchorPageNo = 1
        self.page.add(shape)
        return shape

    def line(self, x1, y1, x2, y2, width=1, color=BLUE):
        shape = self.document.createInstance("com.sun.star.drawing.LineShape")
        shape.LineStyle = self.solid_line
        shape.LineColor = color
        shape.LineWidth = max(1, round(width * 18))
        return self.add(shape, x1, y1, x2 - x1, y2 - y1)

    def rect(self, x1, y1, x2, y2, width=1, radius=0, fill=None):
        shape = self.document.createInstance("com.sun.star.drawing.RectangleShape")
        shape.LineStyle = self.solid_line
        shape.LineColor = BLUE
        shape.LineWidth = max(1, round(width * 18))
        if fill is None:
            shape.FillStyle = self.no_fill
        else:
            shape.FillStyle = self.solid_fill
            shape.FillColor = fill
        if radius:
            shape.CornerRadius = self.x(radius)
        return self.add(shape, x1, y1, x2 - x1, y2 - y1)

    def text(
        self,
        x,
        y,
        width,
        height,
        value,
        font_size=10,
        bold=False,
        color=BLUE,
        align="left",
        vertical="top",
    ):
        shape = self.document.createInstance("com.sun.star.drawing.TextShape")
        shape.LineStyle = self.no_line
        shape.FillStyle = self.no_fill
        self.add(shape, x, y, width, height)
        shape.TextVerticalAdjust = self.vertical_center if vertical == "center" else self.vertical_top
        for name in ("TextLeftDistance", "TextRightDistance", "TextUpperDistance", "TextLowerDistance"):
            setattr(shape, name, 0)
        shape.TextAutoGrowHeight = False
        shape.TextAutoGrowWidth = False
        shape.TextWordWrap = True
        shape.String = value
        cursor = shape.createTextCursor()
        cursor.gotoEnd(True)
        cursor.CharFontName = "DejaVu Sans"
        cursor.CharHeight = font_size * 0.54
        cursor.CharColor = color
        cursor.CharWeight = 150.0 if bold else 100.0
        cursor.ParaAdjust = self.alignments[align]
        return shape

    def centered(self, x1, x2, y, value, font_size=10, bold=False, color=BLUE, height=28):
        return self.text(x1, y, x2 - x1, height, value, font_size, bold, color, "center")

    def field(self, label, x, y, x2, variable, label_width, font_size=12):
        self.text(x, y, label_width, 24, label, font_size)
        self.line(x + label_width, y + 15, x2, y + 15)
        self.text(x + label_width + 4, y - 1, x2 - x - label_width - 8, 25, variable, font_size)

    def checkbox_value(self, x, y, variable, size_value=13):
        self.centered(x, x + size_value, y - 2, variable, 10, True, height=size_value + 6)

    def image(self, path, x, y, width, height):
        graphic = self.graphic_provider.queryGraphic(
            (property_value("URL", uno.systemPathToFileUrl(str(path))),)
        )
        shape = self.document.createInstance("com.sun.star.drawing.GraphicObjectShape")
        shape.Graphic = graphic
        return self.add(shape, x, y, width, height)

    def header(self, logo_path):
        if logo_path:
            self.image(logo_path, 75, 58, 165, 142)
        self.centered(250, 890, 70, "{{empresa_titulo_1}}", 31, True, height=38)
        self.centered(305, 850, 112, "{{empresa_titulo_2}}", 31, True, height=38)
        self.centered(280, 870, 161, "DESARROLLA TU POTENCIAL DE APRENDIZAJE!", 14, height=24)
        self.text(510, 190, 60, 25, "N°.", 17)
        self.text(580, 188, 150, 27, "{{ficha_numero}}", 17, color=RED)

        self.rect(892, 66, 1040, 239, 2, 8)
        for y in (106, 153, 197):
            self.line(892, y, 1040, y)
        self.centered(900, 1035, 78, "FORMA DE PAGO", 10, True, height=20)
        self.text(905, 119, 55, 15, "Quincenal", 7)
        self.rect(960, 118, 971, 129)
        self.checkbox_value(960, 118, "{{convenio_quincenal}}", 11)
        self.text(984, 119, 39, 15, "Mensual", 7)
        self.rect(1023, 118, 1034, 129)
        self.checkbox_value(1023, 118, "{{convenio_mensual}}", 11)
        self.text(940, 140, 83, 15, "1 Solo Pago Total", 7)
        self.rect(1023, 137, 1034, 148)
        self.checkbox_value(1023, 137, "{{convenio_unico}}", 11)
        self.text(900, 167, 132, 18, "FECHA PROXIMA DE PAGO", 8)
        self.centered(900, 1035, 181, "{{fecha_proximo_pago}}", 9, height=18)
        self.text(900, 211, 45, 18, "VALOR", 9)
        self.centered(900, 1035, 223, "{{valor_proximo_pago}}", 9, height=18)

    def identity(self):
        self.field("Cliente:", 60, 255, 635, "{{cliente}}", 54, 12)
        self.field("Fecha:", 642, 255, 878, "{{fecha}}", 50, 12)
        self.field("R.U.C./C.I.:", 60, 300, 380, "{{cliente_identificacion}}", 78, 12)
        self.field("Telf.:", 388, 300, 605, "{{cliente_telefono}}", 37, 12)
        self.field("Cel.:", 617, 300, 858, "{{cliente_celular}}", 34, 12)
        self.field("Edad:", 868, 300, 1040, "{{edad}}", 42, 12)
        self.field("Estudiante:", 60, 348, 610, "{{estudiante}}", 82, 12)
        self.field("C.I.:", 618, 348, 858, "{{estudiante_identificacion}}", 34, 12)
        self.field("Curso/Grado:", 868, 348, 1040, "{{curso_grado}}", 88, 11)
        self.field("Colegio:", 60, 388, 558, "{{colegio}}", 56, 12)
        self.field(
            "Fecha de nacimiento estudiante",
            572,
            388,
            1040,
            "{{estudiante_fecha_nacimiento}}",
            174,
            8,
        )

    def reference_data(self):
        self.rect(60, 407, 1045, 449, 2)
        self.centered(60, 1045, 417, "DATOS REFERENCIALES", 18, True, height=27)
        self.field("Representante:", 82, 466, 510, "{{representante}}", 94, 10)
        self.field("Ocupación:", 503, 466, 767, "{{representante_ocupacion}}", 73, 10)
        self.field("Nota de Grado:", 775, 466, 1040, "{{nota_grado}}", 95, 10)
        self.field("Nombre Conyuge:", 82, 510, 510, "{{nombre_conyuge}}", 110, 10)
        self.field("Ocupación:", 503, 510, 767, "{{ocupacion_conyuge}}", 73, 10)
        self.field("Carrera:", 775, 510, 1040, "{{carrera}}", 56, 10)
        self.field("Dirección:", 82, 555, 767, "{{representante_direccion}}", 68, 10)
        self.field("Universidad:", 775, 555, 1040, "{{universidad}}", 77, 10)
        self.field("Correo estudiante:", 82, 600, 510, "{{estudiante_correo}}", 108, 10)
        self.field("Correo representante:", 503, 600, 1040, "{{representante_correo}}", 125, 10)

        self.rect(63, 629, 1045, 694, 2)
        self.line(410, 629, 410, 694)
        self.line(758, 629, 758, 694)
        self.text(82, 657, 63, 20, "Horario:", 11)
        self.text(145, 657, 250, 20, "{{horario}}", 11)
        self.text(416, 657, 44, 20, "Hora:", 11)
        self.text(460, 657, 250, 20, "{{hora}}", 11)
        self.text(762, 657, 73, 20, "Duración:", 11)
        self.text(835, 657, 190, 20, "{{duracion}}", 11)

    def payment_plan(self):
        left, top, right, bottom = 60, 704, 1045, 1288
        self.rect(left, top, right, bottom, 2, 10)
        self.line(left, 750, right, 750)
        self.centered(left, right, 720, "CONVENIO DE PAGO", 17, True, height=28)
        self.line(left, 801, right, 801)
        self.line(548, 750, 548, 801)
        self.text(72, 762, 200, 18, "Valor Total del Curso", 10)
        self.text(72, 785, 130, 18, "(sin matricula)", 10)
        self.text(562, 770, 146, 20, "Valor de matricula", 10)
        self.text(708, 770, 260, 22, "{{valor_matricula}}", 12)

        header_bottom, data_top, data_bottom = 860, 860, 1136
        columns = [left, 153, 269, 379, 498, 765, 918, 983, right]
        self.line(left, header_bottom, right, header_bottom)
        for x in columns[1:-1]:
            self.line(x, 801, x, header_bottom)
        self.centered(65, 150, 815, "No. De pago", 9, height=18)
        self.centered(158, 264, 812, "Fecha de\npago / debito", 9, height=43)
        self.centered(274, 374, 820, "Valor", 10, height=20)
        self.centered(386, 493, 807, "No. Recibido/\nFactura/Dep.\nBancario", 8, height=50)
        self.text(512, 822, 160, 20, "Observación", 9)
        self.text(773, 822, 80, 20, "Promo:", 10)
        self.centered(918, 983, 822, "SI {{promo_si}}", 9, height=18)
        self.centered(983, right, 822, "NO {{promo_no}}", 9, height=18)

        row_height = (data_bottom - data_top) / 6
        for index in range(7):
            y = data_top + row_height * index
            self.line(left, y, right, y)
        for x in (153, 269, 379, 498):
            self.line(x, data_top, x, data_bottom)
        for index in range(6):
            row_y = data_top + row_height * index + row_height * 0.22
            prefix = f"cuota_{index + 1}"
            self.centered(66, 150, row_y, "{{" + prefix + "_numero}}", 10, height=24)
            self.centered(158, 264, row_y, "{{" + prefix + "_fecha}}", 10, height=24)
            self.centered(274, 374, row_y, "{{" + prefix + "_valor}}", 10, height=24)
            self.text(386, row_y, 104, 24, "{{" + prefix + "_documento}}", 10)
            self.text(510, row_y, 500, 24, "{{" + prefix + "_observacion}}", 10)

        self.text(68, 1154, 57, 20, "ART. 1 YO", 9)
        self.line(125, 1170, 670, 1170)
        self.text(135, 1153, 500, 21, "{{representante}}", 9)
        self.text(682, 1154, 355, 21, "EN CALIDAD DE REPRESENTANTE LEGAL DEL ESTUDIANTE", 9, True)
        self.line(68, 1198, 670, 1198)
        self.text(74, 1179, 570, 21, "{{estudiante}}", 9)
        self.text(682, 1184, 355, 21, "ACEPTO VOLUNTARIAMENTE Y ME COMPROMETO A", 9, True)
        self.text(66, 1210, 930, 20, "CANCELAR EL VALOR TOTAL DEL CURSO DETALLADO EN EL CONVENIO DE PAGO.", 9)
        self.text(66, 1235, 930, 20, "ART.2  AUTORIZO EL USO DE IMAGEN Y FOTOGRAFIAS PARA FINES PUBLICITARIOS.", 9)
        self.text(
            66,
            1260,
            930,
            20,
            "ART. 3  LA GARANTIA TIENE UN 100% DE VALIDEZ SI EL ESTUDIANTE NO TIENE NI UNA SOLA FALTA O ATRASO LOS DIAS DE CLASES.",
            9,
        )
        self.text(66, 1280, 700, 18, "UNA VEZ ACEPTADO EL SERVICIO NO HAY DEVOLUCION DEL DINERO.", 9)

    def footer(self):
        self.rect(50, 1298, 1048, 1450, 2, 8)
        self.line(870, 1298, 870, 1450)
        for y in (1336, 1374, 1412):
            self.line(870, y, 1048, y)
        self.rect(70, 1315, 163, 1335, 0, fill=PALE_BLUE)
        self.text(72, 1316, 100, 18, "FORMA DE PAGO", 10, True)

        payment_fields = (
            ("EFECTIVO", 70, 1344, 152, 1343, "pago_efectivo"),
            ("TRANSFERENCIA", 212, 1344, 350, 1343, "pago_transferencia"),
            ("CHEQUE", 82, 1387, 154, 1386, "pago_cheque"),
            ("TARJETA DE CREDITO", 182, 1387, 347, 1386, "pago_tarjeta"),
            ("DEPOSITO", 82, 1430, 164, 1429, "pago_deposito"),
            ("DEBITO BANCARIO", 198, 1430, 347, 1429, "pago_debito"),
        )
        for label, tx, ty, bx, by, variable in payment_fields:
            self.text(tx, ty, bx - tx, 20, label, 11)
            self.rect(bx, by, bx + 13, by + 13)
            self.checkbox_value(bx, by, "{{" + variable + "}}")

        self.line(388, 1396, 623, 1396)
        self.centered(388, 623, 1406, "FIRMA REPRESENTANTE", 9, height=18)
        self.text(398, 1434, 210, 18, "C.I.: {{representante_identificacion}}", 9)
        self.line(650, 1396, 850, 1396)
        self.centered(650, 850, 1406, "FIRMA DIRECTOR ASESOR", 9, height=18)
        self.text(660, 1434, 180, 18, "C.I.:", 9)

        totals = (("Total", "total"), ("Descuento", "descuento"), ("Abono", "abono"), ("Saldo", "saldo"))
        rows = ((1298, 1336), (1336, 1374), (1374, 1412), (1412, 1450))
        for (label, variable), (y1, y2) in zip(totals, rows):
            self.centered(875, 1044, y1 + 11, f"{label}  {{{{{variable}}}}}", 9, height=y2 - y1 - 8)

        self.rect(48, 1462, 1048, 1557, 2, 7)
        self.text(58, 1476, 28, 28, "⌂", 17, True, align="center")
        self.text(98, 1478, 925, 38, "{{footer_ubicacion}}", 9)
        self.text(58, 1517, 28, 28, "◉", 15, True, align="center")
        self.text(98, 1529, 520, 20, "{{footer_contacto}}", 9)

    def build(self, logo_path):
        self.header(logo_path)
        self.identity()
        self.reference_data()
        self.payment_plan()
        self.footer()


def connect(host, port):
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context
    )
    remote_context = resolver.resolve(
        f"uno:socket,host={host},port={port};urp;StarOffice.ComponentContext"
    )
    service_manager = remote_context.ServiceManager
    desktop = service_manager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", remote_context
    )
    graphic_provider = service_manager.createInstanceWithContext(
        "com.sun.star.graphic.GraphicProvider", remote_context
    )
    return desktop, graphic_provider


def configure_page(document):
    page_style = document.StyleFamilies.getByName("PageStyles").getByName("Standard")
    page_style.Width = PAGE_WIDTH
    page_style.Height = PAGE_HEIGHT
    page_style.LeftMargin = 0
    page_style.RightMargin = 0
    page_style.TopMargin = 0
    page_style.BottomMargin = 0
    page_style.HeaderIsOn = False
    page_style.FooterIsOn = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--logo", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2002)
    args = parser.parse_args()

    desktop, graphic_provider = connect(args.host, args.port)
    document = desktop.loadComponentFromURL(
        "private:factory/swriter", "_blank", 0, ()
    )
    try:
        configure_page(document)
        TemplateBuilder(document, graphic_provider).build(args.logo)
        document.storeAsURL(
            uno.systemPathToFileUrl(str(args.output.resolve())),
            (
                property_value("FilterName", "writer8"),
                property_value("Overwrite", True),
            ),
        )
    finally:
        document.close(True)


if __name__ == "__main__":
    main()
