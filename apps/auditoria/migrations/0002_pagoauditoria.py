# Generated manually for the immutable payment audit trail.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0001_initial"),
        ("cartera", "0004_cuota_change_fecha_pago_debito_permission"),
    ]

    operations = [
        migrations.CreateModel(
            name="PagoAuditoria",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accion", models.CharField(choices=[("crear", "Creación"), ("modificar", "Modificación")], max_length=20)),
                ("pago_id", models.PositiveBigIntegerField(db_index=True)),
                ("empresa_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("cuota_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("plan_pago_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("ficha_inscripcion_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("estudiante_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("forma_pago_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("usuario_pago_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("usuario_accion_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("usuario_accion_username", models.CharField(blank=True, max_length=150)),
                ("datos_anteriores", models.JSONField(blank=True, default=dict)),
                ("datos_nuevos", models.JSONField(blank=True, default=dict)),
                ("cambios", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("metodo_http", models.CharField(blank=True, max_length=10)),
                ("ruta", models.TextField(blank=True)),
                ("user_agent", models.TextField(blank=True)),
                ("created", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "db_table": '"auditoria"."pago_auditoria"',
                "ordering": ["-created", "-pk"],
                "default_permissions": ("view",),
            },
        ),
        migrations.AddIndex(
            model_name="pagoauditoria",
            index=models.Index(fields=["pago_id", "-created"], name="audit_pago_fecha_idx"),
        ),
        migrations.AddIndex(
            model_name="pagoauditoria",
            index=models.Index(fields=["ficha_inscripcion_id", "-created"], name="audit_ficha_fecha_idx"),
        ),
        migrations.AddIndex(
            model_name="pagoauditoria",
            index=models.Index(fields=["usuario_accion_id", "-created"], name="audit_usuario_fecha_idx"),
        ),
    ]
