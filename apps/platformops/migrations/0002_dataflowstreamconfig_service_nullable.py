# Generated manually for the NOC control-plane stream registration.

from django.db import migrations, models
from django.db.models import deletion


class Migration(migrations.Migration):
    dependencies = [("cPlatformIO", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="dataflowstreamconfig",
            name="service",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=deletion.CASCADE,
                to="cPlatformIO.service",
            ),
        ),
    ]
