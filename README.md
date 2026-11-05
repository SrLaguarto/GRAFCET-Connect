# GRAFCET Connect

Editor y simulador de GRAFCET para el aula, basado en IEC 60848, con conexión Modbus TCP a simuladores de procesos.

![Captura de GRAFCET Connect con el ejemplo «Marcha y paro»](docs/imagenes/captura_aula_marcha.png)

## Qué hace

- **Dibujar grafcets:** etapas, transiciones, acciones, simultaneidades, macroetapas, encapsulantes y órdenes de forzado, arrastrándolas desde la paleta.
- **Simular:** pulse las entradas y vea las etapas activas, las salidas, las variables y la traza, con los temporizadores a la vista.
- **Documentar:** planos con hojas y cajetín, que se exportan a PDF o SVG, y el dibujo del grafcet como imagen PNG.
- **Conectar:** como cliente Modbus TCP a un simulador de procesos. Las entradas y salidas del grafcet se asignan a los sensores y actuadores del simulador.
- **Guardar:** cada proyecto es un único archivo `.grafnet`, con una firma que indica si lo guardó esta versión sin cambios.

## Descargar

Para Windows 10 y 11 hay dos opciones en la sección [Releases](https://github.com/SrLaguarto/GRAFCET-Connect/releases) del repositorio:

- **Instalador** `GRAFCET-Connect-1.0.0-setup.exe` (recomendado para la mayoría). Se instala en Archivos de programa (pide permisos de administrador; sin ellos, puede instalarse solo para su usuario), crea el acceso en el menú Inicio, abre los archivos `.grafnet` con doble clic y se desinstala desde Configuración > Aplicaciones.
- **Portable** `GRAFCET-Connect-1.0.0-win64.zip`: descomprima la carpeta entera y ejecute `GRAFCET Connect.exe`. Sirve para un USB o para equipos sin permisos para instalar.

- No necesita conexión a internet.
- La primera vez, Windows puede mostrar «Windows protegió su PC», porque el programa no está firmado digitalmente. Esto ocurre también con el instalador. Para abrirlo, pulse «Más información» y después «Ejecutar de todas formas».

## Primeros pasos

1. **Crear un grafcet.** Abra un ejemplo desde el menú **Ejemplos** o cree un proyecto vacío con **Proyecto > Nuevo proyecto**. Arrastre etapas, transiciones y acciones desde la paleta al dibujo, y únalas arrastrando desde sus puntos de unión. Escriba las receptividades con los bloques del programador o a mano (casilla «Escribir a mano»). Las variables se crean en la tabla de variables, con «Nueva E», «Nueva S» o «Nueva M».
2. **Simular.** Pulse **Play** (F5) para simular y **Stop** para volver a editar; cada Play empieza desde la situación inicial. Pulse las entradas del panel «Simulación» con un clic (Ctrl+clic las enclava). Las etapas activas se ven en el dibujo y las salidas en el panel. Cuándo vale el cambio de una entrada se ajusta en **Ajustes > Ajustes de simulación…**.
3. **Documentar.** En la pestaña **PLANOS**, pulse **+ Añadir hoja** y elija la plantilla en el diálogo. Para exportar, use **Proyecto > Exportar…** (PDF o SVG; en SVG, un archivo por hoja si hay varias). El dibujo del grafcet se guarda como imagen PNG con **Proyecto > Guardar el dibujo como imagen…**.
4. **Conectar con un simulador de procesos.** Abra la pestaña **E/S externas** y pulse **Configuración** para poner la IP, el puerto (502 por defecto) y el esclavo. Para una primera prueba, use **Abrir prueba guiada**. Las variables nuevas se asignan solas a canales libres; también puede arrastrar cada variable a un canal de su lado (entradas a la izquierda, salidas a la derecha). En señales analógicas, use variables Decimal con 2 decimales: una variable Entera recibe el valor redondeado al entero más cercano, con aviso; para el valor exacto, use Decimal (2 decimales). Pulse **Conectar** y, después, **Play**. La guía paso a paso está en [docs/PRIMERA_CONEXION_MODBUS.md](docs/PRIMERA_CONEXION_MODBUS.md).
5. **Abrir y guardar.** **Proyecto > Abrir…** abre un archivo `.grafnet`. **Guardar** (Ctrl+S) y **Guardar como…** lo guardan con su dibujo. **Proyecto > Propiedades del archivo…** muestra el autor, las fechas, las versiones y la firma.

## Firma de los archivos

GRAFCET Connect abre cualquier archivo `.grafnet`. La firma solo indica si el archivo lo guardó esta versión del programa sin cambios. Un archivo sin firma se puede usar con normalidad, y al guardarlo sigue sin firma.

## Comunicar un fallo

Los fallos y las sugerencias se comunican en las [Issues de GitHub](https://github.com/SrLaguarto/GRAFCET-Connect/issues). Indique la versión (**Ayuda > Acerca de GRAFCET Connect…**) y los pasos para reproducirlo.

## Licencia

GRAFCET Connect se publica con la licencia **GPL-3.0**; el texto completo está en el fichero [LICENSE](LICENSE). El autor ofrece además **licencias comerciales bajo petición** para usarlo en un producto o servicio que no pueda cumplir la GPL-3.0; se piden a través de [GitHub](https://github.com/SrLaguarto). Las contribuciones se aceptan según [CONTRIBUTING.md](CONTRIBUTING.md).

Las bibliotecas de Qt (PySide6, LGPL v3) van en el ejecutable como ficheros separados. Sus textos y los de los demás componentes de terceros están en la carpeta `licencias/` del programa. Se ofrece sin ninguna garantía.

## Para desarrolladores

La estructura del código, las comprobaciones, la convención de commits y la procedencia están en [docs/DESARROLLO.md](docs/DESARROLLO.md). Para contribuir, véase [CONTRIBUTING.md](CONTRIBUTING.md).
