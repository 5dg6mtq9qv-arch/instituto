from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_partner_usuario"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="foto",
            field=models.ImageField(blank=True, null=True, upload_to="core/partners/"),
        ),
    ]
