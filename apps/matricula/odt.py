import html
import io
import os
import re
import subprocess
import tempfile
import zipfile
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError


TEMPLATE_PATH = settings.BASE_DIR / "templates_odt" / "matricula_ficha.odt"
SOFFICE_BIN = "/usr/bin/soffice"
SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
LOGO_MEMBER = "Pictures/10000000000000DA000000D10D8D22B23910EC67.png"
REMIXICON_PATH = settings.BASE_DIR / "static" / "assets" / "fonts" / "remixicon.ttf"
ICON_HOME_2_LINE = 0xEE19
ICON_WHATSAPP_LINE = 0xF2BC
PDF_SIZE = (2480, 3508)
REFERENCE_SIZE = (1092, 1600)
BLUE = (22, 65, 122)
RED = (128, 61, 71)


def formato_moneda(value):
    if value in (None, ""):
        return "0.00"
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"
    return f"{amount:.2f}"


def formato_fecha(value):
    return value.strftime("%d/%m/%Y") if value else ""


def checkbox(value):
    return "X" if value else ""


def documento_checkbox(value):
    return "X" if value else ""


def odt_text(value):
    escaped = html.escape(str(value or ""), quote=False)
    return escaped.replace("\n", "<text:line-break/>")


def identificacion_numero(value):
    return re.sub(r"\D", "", str(value or ""))


def get_plan_pago(ficha):
    try:
        return ficha.plan_pago
    except (AttributeError, ObjectDoesNotExist):
        return None


def get_cuotas(ficha):
    plan = get_plan_pago(ficha)
    if not plan:
        return []
    return list(
        plan.cuotas.filter(activo=True)
        .prefetch_related("pagos__forma_pago")
        .order_by("fecha_pago_debito", "numero")
    )


def pago_principal(cuota):
    pagos = list(cuota.pagos.all())
    return pagos[0] if pagos else None


def cuotas_detalle(cuotas):
    detalle = []
    for cuota in cuotas:
        pago = pago_principal(cuota)
        detalle.append(
            {
                "numero": cuota.numero_pago() if hasattr(cuota, "numero_pago") else str(cuota.numero),
                "fecha": formato_fecha(cuota.fecha_pago_debito),
                "valor": formato_moneda(cuota.valor),
                "documento": cuota.numero_recibo_factura_deposito or (pago.numero_documento if pago else "") or "",
                "observacion": cuota.observacion or (pago.comentario if pago else "") or "",
            }
        )
    return detalle


def cuotas_texto(cuotas):
    filas = []
    for cuota in cuotas_detalle(cuotas):
        filas.append(
            " | ".join(
                [
                    cuota["numero"],
                    cuota["fecha"],
                    cuota["valor"],
                    cuota["documento"],
                    cuota["observacion"],
                ]
            )
        )
    return "\n".join(filas)


def primera_forma_pago(cuotas):
    for cuota in cuotas:
        pago = pago_principal(cuota)
        if pago and pago.forma_pago:
            return pago.forma_pago
    return None


def normalizar_forma_pago(forma_pago):
    if not forma_pago:
        return ""
    texto = f"{getattr(forma_pago, 'tipo', '') or ''} {getattr(forma_pago, 'nombre', '') or forma_pago}".lower()
    if "efect" in texto:
        return "efectivo"
    if "transfer" in texto:
        return "transferencia"
    if "cheque" in texto:
        return "cheque"
    if "tarjeta" in texto or "credito" in texto or "crédito" in texto:
        return "tarjeta"
    if "deposit" in texto or "depósito" in texto:
        return "deposito"
    if "debito" in texto or "débito" in texto:
        return "debito"
    return ""


def footer_datos(empresa, empresa_nombre):
    direccion_default = "Av. Carlos Emilio Grijalva entre Juan Genaro Jaramillo y Av. Heleodoro Ayala atrás del nuevo Plásticos y Supermercados San José"
    referencia_default = "(a una cuadra de la Academia Superior Militar y Policial ASMIL)"
    telefono_default = "0989396225 / 0978634977"
    ciudad_default = "Ibarra - Ecuador"
    es_william_james = "WILLIAM JAMES" in (empresa_nombre or "").upper()
    if es_william_james:
        return direccion_default, referencia_default, f"{telefono_default}   {ciudad_default}"

    direccion_lineas = [line.strip() for line in (empresa.direccion or "").splitlines() if line.strip()]
    direccion_1 = direccion_lineas[0] if direccion_lineas else ""
    direccion_2 = direccion_lineas[1] if len(direccion_lineas) > 1 else ""
    telefono = empresa.telefono or ""
    ciudad = empresa.ciudad or ""
    contacto = "   ".join(part for part in [telefono, ciudad] if part)
    return direccion_1, direccion_2, contacto


def ficha_context(ficha):
    cuotas = get_cuotas(ficha)
    forma_pago = ficha.forma_pago_convenio or ""
    estudiante = ficha.estudiante
    representante = ficha.representante or ficha.cliente
    empresa = ficha.empresa
    plan = get_plan_pago(ficha)
    forma_pago_abono = normalizar_forma_pago(primera_forma_pago(cuotas))
    valor_total_curso = ficha.valor_total_curso
    valor_matricula = plan.valor_matricula if plan else ficha.valor_matricula
    descuento = plan.descuento if plan else ficha.descuento
    abono = ficha.abono
    saldo = plan.saldo if plan else ficha.saldo
    valor_total = (
        plan.valor_total
        if plan
        else (valor_total_curso or Decimal("0")) + (valor_matricula or Decimal("0")) - (descuento or Decimal("0"))
    )
    empresa_nombre = empresa.nombre_comercial or empresa.razon_social or ""
    titulo_1, titulo_2 = empresa_titulo(empresa_nombre)
    footer_direccion_1, footer_direccion_2, footer_contacto = footer_datos(empresa, empresa_nombre)
    return {
        "empresa_nombre": empresa_nombre,
        "empresa_titulo_1": titulo_1,
        "empresa_titulo_2": titulo_2,
        "empresa_ruc": empresa.ruc,
        "empresa_direccion": empresa.direccion,
        "empresa_telefono": empresa.telefono,
        "empresa_ciudad": empresa.ciudad,
        "footer_direccion_1": footer_direccion_1,
        "footer_direccion_2": footer_direccion_2,
        "footer_contacto": footer_contacto,
        "ficha_numero": ficha.numero,
        "fecha": formato_fecha(ficha.fecha),
        "cliente": ficha.cliente.nombre if ficha.cliente else "",
        "cliente_identificacion": identificacion_numero(ficha.cliente.identificacion if ficha.cliente else ""),
        "cliente_telefono": ficha.cliente.telefono if ficha.cliente else "",
        "cliente_celular": ficha.cliente.telefono_celular if ficha.cliente else "",
        "estudiante": estudiante.nombre if estudiante else "",
        "estudiante_identificacion": identificacion_numero(estudiante.identificacion if estudiante else ""),
        "estudiante_fecha_nacimiento": formato_fecha(estudiante.fecha_nacimiento) if estudiante else "",
        "estudiante_correo": ficha.correo_estudiante or (estudiante.email if estudiante else ""),
        "edad": ficha.edad,
        "colegio": ficha.colegio,
        "curso_grado": ficha.curso_grado or (ficha.curso.grado if ficha.curso else ""),
        "representante": representante.nombre if representante else "",
        "representante_identificacion": identificacion_numero(representante.identificacion if representante else ""),
        "representante_ocupacion": representante.ocupacion if representante else "",
        "representante_direccion": representante.direccion if representante else "",
        "representante_correo": ficha.correo_representante or (representante.email if representante else ""),
        "nombre_conyuge": ficha.nombre_conyuge,
        "ocupacion_conyuge": ficha.ocupacion_conyuge,
        "nota_grado": ficha.nota_grado,
        "carrera": ficha.carrera or (ficha.curso.carrera if ficha.curso else ""),
        "universidad": ficha.universidad or (ficha.curso.universidad if ficha.curso else ""),
        "horario": ficha.horario,
        "hora": ficha.hora,
        "duracion": ficha.duracion,
        "convenio_quincenal": checkbox(forma_pago == "quincenal"),
        "convenio_mensual": checkbox(forma_pago == "mensual"),
        "convenio_unico": checkbox(forma_pago == "unico"),
        "fecha_proximo_pago": formato_fecha(ficha.fecha_proximo_pago),
        "valor_proximo_pago": formato_moneda(ficha.valor_proximo_pago),
        "valor_total_curso": formato_moneda(valor_total_curso),
        "valor_matricula": formato_moneda(valor_matricula),
        "total": formato_moneda(valor_total),
        "descuento": formato_moneda(descuento),
        "abono": formato_moneda(abono),
        "saldo": formato_moneda(saldo),
        "promo_si": checkbox(ficha.promo),
        "promo_no": checkbox(not ficha.promo),
        "autorizacion_imagen": checkbox(ficha.autorizacion_imagen),
        "acepta_garantia": checkbox(ficha.acepta_garantia),
        "acepta_no_devolucion": checkbox(ficha.acepta_no_devolucion),
        "cuotas": cuotas_texto(cuotas),
        "cuotas_detalle": cuotas_detalle(cuotas),
        "pago_efectivo": documento_checkbox(forma_pago_abono == "efectivo"),
        "pago_transferencia": documento_checkbox(forma_pago_abono == "transferencia"),
        "pago_cheque": documento_checkbox(forma_pago_abono == "cheque"),
        "pago_tarjeta": documento_checkbox(forma_pago_abono == "tarjeta"),
        "pago_deposito": documento_checkbox(forma_pago_abono == "deposito"),
        "pago_debito": documento_checkbox(forma_pago_abono == "debito"),
    }


def empresa_titulo(nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        return "", ""
    upper = nombre.upper()
    if "WILLIAM JAMES" in upper:
        return "CENTRO DE APRENDIZAJE INTEGRAL", "WILLIAM JAMES S."
    palabras = upper.split()
    if len(palabras) <= 4:
        return upper, ""
    mitad = (len(palabras) + 1) // 2
    return " ".join(palabras[:mitad]), " ".join(palabras[mitad:])


def render_odt(template_path, output_path, context):
    if not template_path.exists():
        raise FileNotFoundError(f"No existe la plantilla ODT: {template_path}")
    with zipfile.ZipFile(template_path, "r") as source, zipfile.ZipFile(output_path, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "content.xml":
                text = data.decode("utf-8")
                for key, value in context.items():
                    text = text.replace("{{" + key + "}}", odt_text(value))
                data = text.encode("utf-8")
            target.writestr(item, data)


def render_ficha_odt(ficha, output_path):
    render_odt(TEMPLATE_PATH, output_path, ficha_context(ficha))


@lru_cache(maxsize=None)
def document_font(size, bold=False):
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
        ),
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


@lru_cache(maxsize=None)
def icon_font(size):
    if REMIXICON_PATH.is_file():
        return ImageFont.truetype(str(REMIXICON_PATH), size)
    return None


def load_logo():
    if not TEMPLATE_PATH.exists():
        return None
    try:
        with zipfile.ZipFile(TEMPLATE_PATH, "r") as template:
            with template.open(LOGO_MEMBER) as logo_file:
                image = Image.open(io.BytesIO(logo_file.read())).convert("RGBA")
    except (KeyError, OSError, UnidentifiedImageError, zipfile.BadZipFile):
        return None
    crop_bottom = min(image.height, int(image.width * 0.78))
    crop_right = min(image.width, int(crop_bottom * 1.08))
    return image.crop((0, 0, crop_right, crop_bottom))


class FichaPdfDrawer:
    def __init__(self, context):
        self.context = context
        self.width, self.height = PDF_SIZE
        self.ref_width, self.ref_height = REFERENCE_SIZE
        self.image = Image.new("RGB", PDF_SIZE, "white")
        self.draw = ImageDraw.Draw(self.image)
        self.scale = (self.width / self.ref_width + self.height / self.ref_height) / 2

    def x(self, value):
        return int(round(value * self.width / self.ref_width))

    def y(self, value):
        return int(round(value * self.height / self.ref_height))

    def w(self, value):
        return max(1, int(round(value * self.scale)))

    def font(self, size, bold=False):
        return document_font(max(1, self.w(size)), bold=bold)

    def line(self, points, width=1):
        self.draw.line([(self.x(x), self.y(y)) for x, y in points], fill=BLUE, width=self.w(width))

    def rect(self, coords, width=1, radius=0):
        x1, y1, x2, y2 = coords
        box = (self.x(x1), self.y(y1), self.x(x2), self.y(y2))
        if radius:
            self.draw.rounded_rectangle(box, radius=self.w(radius), outline=BLUE, width=self.w(width))
        else:
            self.draw.rectangle(box, outline=BLUE, width=self.w(width))

    def text_width(self, text, font):
        bbox = self.draw.textbbox((0, 0), str(text), font=font)
        return bbox[2] - bbox[0]

    def fit_font(self, text, size, max_width, bold=False, min_size=6):
        current_size = size
        while current_size > min_size:
            font = self.font(current_size, bold)
            if self.text_width(text, font) <= self.x(max_width):
                return font
            current_size -= 1
        return self.font(min_size, bold)

    def truncate(self, text, font, max_width):
        text = str(text or "")
        if self.text_width(text, font) <= self.x(max_width):
            return text
        suffix = "..."
        low, high = 0, len(text)
        while low < high:
            mid = (low + high) // 2
            if self.text_width(text[:mid] + suffix, font) <= self.x(max_width):
                low = mid + 1
            else:
                high = mid
        return text[: max(0, low - 1)].rstrip() + suffix

    def text(self, x, y, value, size=11, bold=False, fill=BLUE, max_width=None, min_size=6):
        value = str(value or "")
        font = self.fit_font(value, size, max_width, bold, min_size) if max_width else self.font(size, bold)
        if max_width:
            value = self.truncate(value, font, max_width)
        self.draw.text((self.x(x), self.y(y)), value, font=font, fill=fill)

    def full_text(self, x, y, value, size=11, bold=False, fill=BLUE, max_width=None, min_size=5):
        value = str(value or "")
        font = self.fit_font(value, size, max_width, bold, min_size) if max_width else self.font(size, bold)
        self.draw.text((self.x(x), self.y(y)), value, font=font, fill=fill)

    def wrap_text_lines(self, value, size, max_width, bold=False):
        words = str(value or "").split()
        if not words:
            return []
        font = self.font(size, bold)
        lines = []
        current = ""
        max_width_px = self.x(max_width)
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and self.text_width(candidate, font) > max_width_px:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def wrapped_full_text(self, x, y, value, size=9, max_width=900, line_height=22, bold=False):
        lines = self.wrap_text_lines(value, size, max_width, bold=bold)
        for index, line in enumerate(lines):
            self.full_text(x, y + line_height * index, line, size=size, bold=bold)
        return y + line_height * len(lines)

    def center_text(self, x1, x2, y, value, size=11, bold=False, fill=BLUE, max_width=None):
        value = str(value or "")
        available = max_width or (x2 - x1 - 4)
        font = self.fit_font(value, size, available, bold)
        value = self.truncate(value, font, available)
        width = self.text_width(value, font)
        x = self.x(x1) + (self.x(x2 - x1) - width) / 2
        self.draw.text((int(x), self.y(y)), value, font=font, fill=fill)

    def checkbox(self, x, y, checked=False, size=13):
        x1, y1 = self.x(x), self.y(y)
        side = self.w(size)
        self.draw.rectangle((x1, y1, x1 + side, y1 + side), outline=BLUE, width=self.w(1))
        if checked:
            self.draw.line(
                (x1 + self.w(3), y1 + self.w(7), x1 + self.w(6), y1 + self.w(11)),
                fill=BLUE,
                width=self.w(1),
            )
            self.draw.line(
                (x1 + self.w(6), y1 + self.w(11), x1 + self.w(11), y1 + self.w(3)),
                fill=BLUE,
                width=self.w(1),
            )

    def icon_glyph(self, x, y, codepoint, size):
        font = icon_font(self.w(size))
        if not font:
            return False
        text = chr(codepoint)
        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        px = self.x(x) - text_width / 2 - bbox[0]
        py = self.y(y) - text_height / 2 - bbox[1]
        self.draw.text((int(px), int(py)), text, font=font, fill=BLUE)
        return True

    def footer_house_icon(self, x, y):
        cx, cy, radius = self.x(x), self.y(y), self.w(12)
        self.draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=BLUE, width=self.w(2))
        if self.icon_glyph(x, y + 1, ICON_HOME_2_LINE, 14):
            return
        roof = [
            (self.x(x - 6), self.y(y + 1)),
            (self.x(x), self.y(y - 6)),
            (self.x(x + 6), self.y(y + 1)),
        ]
        self.draw.line(roof, fill=BLUE, width=self.w(2), joint="curve")
        self.draw.rectangle((self.x(x - 5), self.y(y + 1), self.x(x + 5), self.y(y + 8)), outline=BLUE, width=self.w(2))
        self.draw.rectangle((self.x(x - 1), self.y(y + 4), self.x(x + 2), self.y(y + 8)), outline=BLUE, width=self.w(1))

    def footer_whatsapp_icon(self, x, y):
        if self.icon_glyph(x, y, ICON_WHATSAPP_LINE, 26):
            return
        cx, cy, radius = self.x(x), self.y(y), self.w(12)
        self.draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=BLUE, width=self.w(2))
        tail = [(self.x(x - 7), self.y(y + 8)), (self.x(x - 12), self.y(y + 12)), (self.x(x - 5), self.y(y + 10))]
        self.draw.line(tail, fill=BLUE, width=self.w(2), joint="curve")
        self.draw.arc(
            (self.x(x - 5), self.y(y - 5), self.x(x + 7), self.y(y + 7)),
            start=120,
            end=310,
            fill=BLUE,
            width=self.w(2),
        )
        self.draw.line((self.x(x - 2), self.y(y + 4), self.x(x + 5), self.y(y + 7)), fill=BLUE, width=self.w(2))

    def field(self, label, x, y, x2, value="", label_width=None, size=12):
        label_width = label_width if label_width is not None else 8 + len(label) * 6
        self.text(x, y, label, size=size)
        self.line([(x + label_width, y + 15), (x2, y + 15)], width=1)
        if value not in (None, ""):
            self.text(x + label_width + 4, y - 1, value, size=size, max_width=x2 - x - label_width - 8, min_size=7)

    def payment_box_checked(self, key):
        return bool(self.context.get(key))

    def draw_header(self):
        logo = load_logo()
        if logo:
            logo = logo.resize((self.x(165), self.y(142)), Image.Resampling.LANCZOS)
            self.image.paste(logo, (self.x(75), self.y(58)), logo)
        self.center_text(250, 890, 70, self.context["empresa_titulo_1"], size=31, bold=True)
        self.center_text(305, 850, 112, self.context["empresa_titulo_2"], size=31, bold=True)
        self.center_text(280, 870, 161, "DESARROLLA TU POTENCIAL DE APRENDIZAJE!", size=14)
        self.text(510, 190, "N°.", size=17)
        self.text(580, 188, self.context["ficha_numero"], size=17, fill=RED, max_width=150)

        self.rect((892, 66, 1040, 239), width=2, radius=8)
        self.line([(892, 106), (1040, 106)], width=1)
        self.line([(892, 153), (1040, 153)], width=1)
        self.line([(892, 197), (1040, 197)], width=1)
        self.center_text(900, 1035, 78, "FORMA DE PAGO", size=10, bold=True)
        self.text(905, 119, "Quincenal", size=7)
        self.checkbox(960, 118, self.context["convenio_quincenal"] == "X", size=11)
        self.text(984, 119, "Mensual", size=7)
        self.checkbox(1023, 118, self.context["convenio_mensual"] == "X", size=11)
        self.text(940, 140, "1 Solo Pago Total", size=7)
        self.checkbox(1023, 137, self.context["convenio_unico"] == "X", size=11)
        self.text(900, 167, "FECHA PROXIMA DE PAGO", size=8, max_width=132)
        self.center_text(900, 1035, 181, self.context["fecha_proximo_pago"], size=9)
        self.text(900, 211, "VALOR", size=9)
        self.center_text(900, 1035, 223, self.context["valor_proximo_pago"], size=9)

    def draw_identity(self):
        self.field("Cliente:", 60, 255, 635, self.context["cliente"], label_width=54, size=12)
        self.field("Fecha:", 642, 255, 878, self.context["fecha"], label_width=50, size=12)
        self.field("R.U.C./C.I.:", 60, 300, 380, self.context["cliente_identificacion"], label_width=78, size=12)
        self.field("Telf.:", 388, 300, 605, self.context["cliente_telefono"], label_width=37, size=12)
        self.field("Cel.:", 617, 300, 858, self.context["cliente_celular"], label_width=34, size=12)
        self.field("Edad:", 868, 300, 1040, self.context["edad"], label_width=42, size=12)
        self.field("Estudiante:", 60, 348, 610, self.context["estudiante"], label_width=82, size=12)
        self.field("C.I.:", 618, 348, 858, self.context["estudiante_identificacion"], label_width=34, size=12)
        self.field("Curso/Grado:", 868, 348, 1040, self.context["curso_grado"], label_width=88, size=11)
        self.field("Colegio:", 60, 388, 558, self.context["colegio"], label_width=56, size=12)
        self.field(
            "Fecha de nacimiento estudiante",
            572,
            388,
            1040,
            self.context["estudiante_fecha_nacimiento"],
            label_width=174,
            size=8,
        )

    def draw_reference_data(self):
        self.rect((60, 407, 1045, 449), width=2)
        self.center_text(60, 1045, 417, "DATOS REFERENCIALES", size=18, bold=True)
        self.field("Representante:", 82, 466, 510, self.context["representante"], label_width=94, size=10)
        self.field("Ocupación:", 503, 466, 767, self.context["representante_ocupacion"], label_width=73, size=10)
        self.field("Nota de Grado:", 775, 466, 1040, self.context["nota_grado"], label_width=95, size=10)
        self.field("Nombre Conyuge:", 82, 510, 510, self.context["nombre_conyuge"], label_width=110, size=10)
        self.field("Ocupación:", 503, 510, 767, self.context["ocupacion_conyuge"], label_width=73, size=10)
        self.field("Carrera:", 775, 510, 1040, self.context["carrera"], label_width=56, size=10)
        self.field("Dirección:", 82, 555, 767, self.context["representante_direccion"], label_width=68, size=10)
        self.field("Universidad:", 775, 555, 1040, self.context["universidad"], label_width=77, size=10)
        self.field("Correo estudiante:", 82, 600, 510, self.context["estudiante_correo"], label_width=108, size=10)
        self.field("Correo representante:", 503, 600, 1040, self.context["representante_correo"], label_width=125, size=10)

        self.rect((63, 629, 1045, 694), width=2)
        self.line([(410, 629), (410, 694)], width=1)
        self.line([(758, 629), (758, 694)], width=1)
        self.text(82, 657, "Horario:", size=11)
        self.text(145, 657, self.context["horario"], size=11, max_width=250)
        self.text(416, 657, "Hora:", size=11)
        self.text(460, 657, self.context["hora"], size=11, max_width=250)
        self.text(762, 657, "Duración:", size=11)
        self.text(835, 657, self.context["duracion"], size=11, max_width=190)

    def draw_payment_plan(self):
        left, top, right, bottom = 60, 704, 1045, 1288
        self.rect((left, top, right, bottom), width=2, radius=10)
        self.line([(left, 750), (right, 750)], width=1)
        self.center_text(left, right, 720, "CONVENIO DE PAGO", size=17, bold=True)

        self.line([(left, 801), (right, 801)], width=1)
        self.line([(548, 750), (548, 801)], width=1)
        self.text(72, 762, "Valor Total del Curso", size=10)
        self.text(72, 785, "(sin matricula)", size=10)
        self.text(210, 777, self.context["valor_total_curso"], size=12, max_width=240)
        self.text(562, 770, "Valor de matricula", size=10)
        self.text(708, 770, self.context["valor_matricula"], size=12, max_width=260)

        header_bottom = 860
        data_top = header_bottom
        data_bottom = 1136
        columns = [left, 153, 269, 379, 498, 765, 918, 983, right]
        self.line([(left, header_bottom), (right, header_bottom)], width=1)
        for x in columns[1:-1]:
            self.line([(x, 801), (x, header_bottom)], width=1)
        self.center_text(65, 150, 815, "No. De pago", size=9)
        self.center_text(158, 264, 812, "Fecha de", size=9)
        self.center_text(158, 264, 836, "pago / debito", size=9)
        self.center_text(274, 374, 820, "Valor", size=10)
        self.center_text(386, 493, 809, "No. Recibido/", size=8)
        self.center_text(386, 493, 830, "Factura/Dep.", size=8)
        self.center_text(386, 493, 850, "Bancario", size=8)
        self.text(512, 822, "Observación", size=9)
        self.text(773, 822, "Promo:", size=10)
        self.center_text(918, 983, 822, f"SI {self.context['promo_si']}".strip(), size=9)
        self.center_text(983, right, 822, f"NO {self.context['promo_no']}".strip(), size=9)

        detalles = self.context["cuotas_detalle"]
        row_count = max(6, len(detalles))
        row_height = (data_bottom - data_top) / row_count
        for index in range(row_count + 1):
            y = data_top + row_height * index
            self.line([(left, y), (right, y)], width=1)
        for x in [153, 269, 379, 498]:
            self.line([(x, data_top), (x, data_bottom)], width=1)

        body_size = 10 if row_height >= 34 else 8
        for index, cuota in enumerate(detalles):
            row_y = data_top + row_height * index + max(5, row_height * 0.25)
            self.center_text(66, 150, row_y, cuota["numero"], size=body_size)
            self.center_text(158, 264, row_y, cuota["fecha"], size=body_size)
            self.center_text(274, 374, row_y, cuota["valor"], size=body_size)
            self.text(386, row_y, cuota["documento"], size=body_size, max_width=104)
            self.text(510, row_y, cuota["observacion"], size=body_size, max_width=515)

        self.text(68, 1154, "ART. 1 YO", size=9)
        self.line([(125, 1170), (670, 1170)], width=1)
        self.text(135, 1153, self.context["representante"], size=9, max_width=500)
        self.text(682, 1154, "EN CALIDAD DE REPRESENTANTE LEGAL DEL ESTUDIANTE", size=9, bold=True)
        self.line([(68, 1198), (670, 1198)], width=1)
        self.text(74, 1179, self.context["estudiante"], size=9, max_width=570)
        self.text(682, 1184, "ACEPTO VOLUNTARIAMENTE Y ME COMPROMETO A", size=9, bold=True)
        self.text(66, 1210, "CANCELAR EL VALOR TOTAL DEL CURSO DETALLADO EN EL CONVENIO DE PAGO.", size=9)
        self.text(66, 1235, "ART.2  AUTORIZO EL USO DE IMAGEN Y FOTOGRAFIAS PARA FINES PUBLICITARIOS.", size=9)
        self.text(
            66,
            1260,
            "ART. 3  LA GARANTIA TIENE UN 100% DE VALIDEZ SI EL ESTUDIANTE "
            "NO TIENE NI UNA SOLA FALTA O ATRASO LOS DIAS DE CLASES.",
            size=9,
        )
        self.text(66, 1280, "UNA VEZ ACEPTADO EL SERVICIO NO HAY DEVOLUCION DEL DINERO.", size=9)

    def draw_footer(self):
        self.rect((50, 1298, 1048, 1450), width=2, radius=8)
        self.line([(870, 1298), (870, 1450)], width=1)
        for y in [1336, 1374, 1412]:
            self.line([(870, y), (1048, y)], width=1)

        self.draw.rectangle((self.x(70), self.y(1315), self.x(163), self.y(1335)), fill=(227, 235, 249))
        self.text(72, 1316, "FORMA DE PAGO", size=10, bold=True)
        self.text(70, 1344, "EFECTIVO", size=11)
        self.checkbox(152, 1343, self.payment_box_checked("pago_efectivo"), size=13)
        self.text(212, 1344, "TRANSFERENCIA", size=11)
        self.checkbox(350, 1343, self.payment_box_checked("pago_transferencia"), size=13)
        self.text(82, 1387, "CHEQUE", size=11)
        self.checkbox(154, 1386, self.payment_box_checked("pago_cheque"), size=13)
        self.text(182, 1387, "TARJETA DE CREDITO", size=11)
        self.checkbox(347, 1386, self.payment_box_checked("pago_tarjeta"), size=13)
        self.text(82, 1430, "DEPOSITO", size=11)
        self.checkbox(164, 1429, self.payment_box_checked("pago_deposito"), size=13)
        self.text(198, 1430, "DEBITO BANCARIO", size=11)
        self.checkbox(347, 1429, self.payment_box_checked("pago_debito"), size=13)

        self.line([(388, 1396), (623, 1396)], width=1)
        self.center_text(388, 623, 1406, "FIRMA REPRESENTANTE", size=9)
        self.text(398, 1434, f"C.I.: {self.context['representante_identificacion']}", size=9, max_width=210)
        self.line([(650, 1396), (850, 1396)], width=1)
        self.center_text(650, 850, 1406, "FIRMA DIRECTOR ASESOR", size=9)
        self.text(660, 1434, "C.I.:", size=9)

        totals = [
            ("Total", self.context["total"]),
            ("Descuento", self.context["descuento"]),
            ("Abono", self.context["abono"]),
            ("Saldo", self.context["saldo"]),
        ]
        total_rows = [(1298, 1336), (1336, 1374), (1374, 1412), (1412, 1450)]
        for (label, value), (y1, y2) in zip(totals, total_rows):
            text = f"{label}  {value}" if value else label
            self.center_text(875, 1044, y1 + 11, text, size=9)

        self.rect((48, 1462, 1048, 1557), width=2, radius=7)
        self.footer_house_icon(72, 1490)
        footer_ubicacion = " ".join(
            part for part in [self.context["footer_direccion_1"], self.context["footer_direccion_2"]] if part
        )
        contacto_y = self.wrapped_full_text(98, 1478, footer_ubicacion, size=9, max_width=925, line_height=25) + 4
        self.footer_whatsapp_icon(72, 1531)
        self.full_text(98, max(1529, contacto_y), self.context["footer_contacto"], size=9, max_width=520)

    def save(self, output_path):
        self.draw_header()
        self.draw_identity()
        self.draw_reference_data()
        self.draw_payment_plan()
        self.draw_footer()
        self.image.save(output_path, "PDF", resolution=300.0)


def render_ficha_pdf(ficha, output_path):
    FichaPdfDrawer(ficha_context(ficha)).save(output_path)


def convert_odt_to_pdf(odt_path, output_dir):
    if not Path(SOFFICE_BIN).is_file():
        raise RuntimeError("No se encontró LibreOffice en /usr/bin/soffice.")

    entorno = os.environ.copy()
    entorno["HOME"] = "/tmp"
    entorno["PATH"] = SYSTEM_PATH

    with tempfile.TemporaryDirectory(prefix="libreoffice_") as profile_dir:
        result = subprocess.run(
            [
                SOFFICE_BIN,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                f"-env:UserInstallation={Path(profile_dir).as_uri()}",
                "--convert-to",
                "pdf:writer_pdf_Export",
                "--outdir",
                str(output_dir),
                str(odt_path),
            ],
            env=entorno,
            capture_output=True,
            text=True,
            timeout=120,
        )
    if result.returncode != 0:
        raise RuntimeError(f"Error al convertir con LibreOffice: {result.stderr or result.stdout}")
    return Path(output_dir) / (Path(odt_path).stem + ".pdf")


def build_document_response_file(ficha, extension):
    temp_dir = tempfile.TemporaryDirectory()
    base_name = f"matricula_{ficha.numero}"
    if extension == "pdf":
        pdf_path = Path(temp_dir.name) / f"{base_name}.pdf"
        render_ficha_pdf(ficha, pdf_path)
        return temp_dir, pdf_path
    odt_path = Path(temp_dir.name) / f"{base_name}.odt"
    render_ficha_odt(ficha, odt_path)
    return temp_dir, odt_path
