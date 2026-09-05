# Integración Moodle

En **Coordinación → Temas y subtemas**, el permiso
`academico.crear_moodlecurso` muestra **Crear curso en Moodle** por materia/grupo.
La migración 0040 registra el enlace al curso. El grupo Coordinacion recibe el
permiso a través del mecanismo existente de permisos por defecto; Administrador
lo recibe también. Se puede asignar individualmente desde la gestión de permisos.

El botón abre una revisión de docentes, alumnos y temario. Solo el POST de esa
pantalla crea el curso. Se exige al menos un tema de planificación, un docente
activo asignado y alumnos activos en el grupo, con correos válidos cuando estén registrados y sin
correos personales compartidos entre personas diferentes.

Las cuentas nuevas de Moodle usan el primer nombre y primer apellido normalizados
(`juan_perez`, `juan_perez1`, etc.). Se comprueba disponibilidad local y remota.
La vinculación persona/instancia y el ID Moodle se conservan entre materias. Si ya
existe una cuenta con el correo de la persona, se reutiliza sin cambiar su clave.
Si la persona no tiene correo, se usa `usuario@felixiot.site` únicamente en Moodle.
`MOODLE_FALLBACK_EMAIL_DOMAIN` permite configurar ese dominio. Se comprueba que
la dirección provisional no pertenezca a otra cuenta; en caso de coincidencia
se añade un número al usuario. Los correos personales registrados se conservan.

`MOODLE_INITIAL_PASSWORD` define la clave temporal común de las cuentas nuevas.
Moodle recibe `auth_forcepasswordchange=1` y exige cambiarla al entrar. No se envían
correos de bienvenida. Las claves iniciales se guardan cifradas mediante Fernet;
la clave de cifrado se deriva de `SECRET_KEY`. Al rotarla, conservar la anterior
en `SECRET_KEY_FALLBACKS` para descifrar registros existentes. La integración no
conoce ni almacena la contraseña personal elegida posteriormente en Moodle.

El permiso `academico.exportar_moodlecuenta` habilita **Excel de accesos** por
materia/grupo para Director, Direccion y Administrador. Incluye nombre,
identificación, rol, usuario, clave inicial, URL y estado de matrícula. Las cuentas
existentes llevan la clave vacía. La descarga no restablece contraseñas ni modifica
Moodle. Los valores se escriben como texto, y la respuesta impide almacenamiento
en caché. La columna identifica la clave como inicial, no como contraseña vigente.

## Configuración

En `.env`: `MOODLE_BASE_URL`, `MOODLE_TOKEN`, `MOODLE_TIMEOUT` (20 segundos por
petición), `MOODLE_CATEGORY_ID` (1), `MOODLE_TEACHER_ROLE_ID` (3) y
`MOODLE_STUDENT_ROLE_ID` (5). Los valores de roles corresponden a los roles
estándar profesor editor y estudiante: comprobarlos si la instalación personalizó
los roles. La matriculación manual debe estar habilitada para los cursos nuevos.

Ejecutar `python manage.py migrate` al desplegar y
`python manage.py comprobar_moodle` para comprobar las nueve funciones del servicio.
Nunca guardar tokens en archivos versionados.

## Alcance y reintentos

El curso conserva el temario ordenado en su resumen y además crea cada tema como
una sección principal. Cada subtema se crea como una actividad **Subsección** de
Moodle 5.1 dentro de su tema. El docente agrega manualmente los demás recursos y
actividades. El botón **Sincronizar temario** incorpora elementos faltantes sin
borrar contenido creado por el docente. No elimina automáticamente secciones o
subsecciones retiradas del instituto y no sincroniza calificaciones.

La clave de curso se persiste antes de la primera llamada y se utiliza como
nombre corto único en Moodle. Un bloqueo de fila serializa las creaciones para
la misma materia/grupo. Ante errores de red se busca ese nombre antes de volver
a crear. Si falla la matrícula se conserva el identificador y el botón permite
completarla. No se borran cursos ni usuarios al fallar. Si termina, el botón pasa
a **Abrir curso en Moodle**. El proceso es síncrono: ajustar el tiempo de espera
del servidor web para grupos grandes.
