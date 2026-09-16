# Cierre automático de asistencias

El comando `python manage.py cerrar_asistencias_vencidas` cierra las clases cuya fecha
es anterior al día actual en la zona horaria configurada por Django
(`America/Guayaquil`). Conserva las marcas de los alumnos y deja sin registro a
quienes no tengan una marca; no los considera ausentes automáticamente. El cierre
queda identificado como automático, sin un docente en «Cerrada por».

La tarea es idempotente: solo modifica clases que aún están abiertas. En el
servidor donde corre la aplicación, ejecútala cada cinco minutos. El comando
usa la zona horaria de Django, así que la programación funciona aunque el
reloj del servidor esté en UTC.

Si el entorno se activa con `workon instituto`, confirma su ejecutable con:

```bash
workon instituto
command -v python
```

Normalmente será `/home/USUARIO/.virtualenvs/instituto/bin/python`. En cron
se usa directamente ese ejecutable; no hace falta ejecutar `workon`. Si el
proyecto está en `/srv/instituto`, la entrada para el mismo usuario que creó
el entorno es:

```cron
*/5 * * * * cd /srv/instituto && $HOME/.virtualenvs/instituto/bin/python manage.py cerrar_asistencias_vencidas >> /srv/instituto/logs/cierre_asistencias.log 2>&1
```

Sustituye `/srv/instituto` por la ruta real del proyecto. Antes de activar el
cron, aplica las migraciones y crea el directorio de logs:

```bash
cd /srv/instituto
$HOME/.virtualenvs/instituto/bin/python manage.py migrate
mkdir -p logs
$HOME/.virtualenvs/instituto/bin/python manage.py cerrar_asistencias_vencidas
crontab -e
```

Agrega la línea cron, guarda y comprueba la instalación con `crontab -l`.
