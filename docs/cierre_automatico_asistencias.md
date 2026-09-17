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

En el servidor `preuniversitario`, el ejecutable confirmado es
`/home/preuniversitario/.virtualenvs/instituto/bin/python`. En cron se usa
directamente ese ejecutable; no hace falta ejecutar `workon`. La entrada para
ese servidor es:

```cron
*/5 * * * * cd /home/preuniversitario/Dev/instituto && /home/preuniversitario/.virtualenvs/instituto/bin/python manage.py cerrar_asistencias_vencidas >> /home/preuniversitario/Dev/instituto/logs/cierre_asistencias.log 2>&1
```

Antes de activar el cron, aplica las migraciones y crea el directorio de logs:

```bash
cd /home/preuniversitario/Dev/instituto
/home/preuniversitario/.virtualenvs/instituto/bin/python manage.py migrate
mkdir -p logs
/home/preuniversitario/.virtualenvs/instituto/bin/python manage.py cerrar_asistencias_vencidas
crontab -e
```

Agrega la línea cron, guarda y comprueba la instalación con `crontab -l`.
