import html
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings


TEMPLATE_PATH = settings.BASE_DIR / "templates_odt" / "matricula_ficha.odt"


def formato_moneda(value):
    return f"{value:.2f}" if value is not None else "0.00"


def formato_fecha(value):
    return value.strftime("%d/%m/%Y") if value else ""


def checkbox(value):
    return "X" if value else ""


def odt_text(value):
    escaped = html.escape(str(value or ""), quote=False)
    return escaped.replace("\n", "<text:line-break/>")


def cuotas_texto(cuotas):
    filas = []
    for cuota in cuotas:
        filas.append(
            " | ".join(
                [
                    str(cuota.numero),
                    formato_fecha(cuota.fecha_pago_debito),
                    formato_moneda(cuota.valor),
                    cuota.numero_recibo_factura_deposito or "",
                    cuota.observacion or "",
                ]
            )
        )
    return "\n".join(filas)


def ficha_context(ficha):
    cuotas = list(ficha.plan_pago.cuotas.all()) if hasattr(ficha, "plan_pago") else []
    forma_pago = ficha.forma_pago_convenio or ""
    estudiante = ficha.estudiante
    representante = ficha.representante or ficha.cliente
    empresa = ficha.empresa
    plan = ficha.plan_pago if hasattr(ficha, "plan_pago") else None
    return {
        "empresa_nombre": empresa.nombre_comercial or empresa.razon_social or "",
        "empresa_ruc": empresa.ruc,
        "empresa_direccion": empresa.direccion,
        "empresa_telefono": empresa.telefono,
        "empresa_ciudad": empresa.ciudad,
        "ficha_numero": ficha.numero,
        "fecha": formato_fecha(ficha.fecha),
        "cliente": ficha.cliente.nombre if ficha.cliente else "",
        "cliente_identificacion": ficha.cliente.identificacion if ficha.cliente else "",
        "cliente_telefono": ficha.cliente.telefono if ficha.cliente else "",
        "cliente_celular": ficha.cliente.telefono_celular if ficha.cliente else "",
        "estudiante": estudiante.nombre if estudiante else "",
        "estudiante_identificacion": estudiante.identificacion if estudiante else "",
        "estudiante_fecha_nacimiento": formato_fecha(estudiante.fecha_nacimiento) if estudiante else "",
        "estudiante_correo": ficha.correo_estudiante or (estudiante.email if estudiante else ""),
        "edad": ficha.edad,
        "colegio": ficha.colegio,
        "curso_grado": ficha.curso_grado or (ficha.curso.grado if ficha.curso else ""),
        "representante": representante.nombre if representante else "",
        "representante_identificacion": representante.identificacion if representante else "",
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
        "valor_total_curso": "",
        "valor_matricula": "",
        "total": "",
        "descuento": "",
        "abono": formato_moneda(ficha.abono),
        "saldo": formato_moneda(ficha.saldo),
        "promo_si": checkbox(ficha.promo),
        "promo_no": checkbox(not ficha.promo),
        "autorizacion_imagen": checkbox(ficha.autorizacion_imagen),
        "acepta_garantia": checkbox(ficha.acepta_garantia),
        "acepta_no_devolucion": checkbox(ficha.acepta_no_devolucion),
        "cuotas": cuotas_texto(cuotas),
    }


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


def convert_odt_to_pdf(odt_path, output_dir):
    binary = shutil.which("soffice") or shutil.which("libreoffice")
    if not binary:
        raise RuntimeError("LibreOffice no esta instalado en el servidor.")

    with tempfile.TemporaryDirectory(prefix="libreoffice_") as profile_dir:
        result = subprocess.run(
            [
                binary,
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
            env={
                **os.environ,
                "HOME": "/tmp",
            },
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
    odt_path = Path(temp_dir.name) / f"{base_name}.odt"
    render_ficha_odt(ficha, odt_path)
    if extension == "odt":
        return temp_dir, odt_path
    pdf_path = convert_odt_to_pdf(odt_path, temp_dir.name)
    return temp_dir, pdf_path
