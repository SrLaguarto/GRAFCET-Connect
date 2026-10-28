# Traspaso entre sesiones

Nota para la siguiente conversación de Claude Code (coordinador). Estado al 28-10-2026.

## Dónde está el trabajo

- Rama en uso: `claude/paso5-memorias-bloques`, creada desde `claude/awesome-mendel-kld8yv` (no está fusionada en
  `main`). La siguiente sesión parte de ella.
- Pasos 1 a 4 de `docs/Plan_de_trabajo_Sonnet.md` hechos. Últimas decisiones: P-IMP-36 (tramos verticales mínimos,
  transición que se agarra sin sacar rama), P-IMP-37 (sin escalones, una flecha por lazo, imán, panel izquierdo
  plegable, arrastre visible desde la paleta), P-IMP-38 (paso 4: variables, acciones de etapa y un primer
  programador por bloques), P-IMP-39 (memorias, programador por bloques tipo Scratch y correcciones del paso 4) P-IMP-40 (programador en el panel inferior, pestaña «Bloques»; «y»/«o» de colores distintos; ficha «Acción» en la
  paleta) y P-IMP-41 (arrastre de la paleta arreglado, fórmula abajo, lazo, acciones que se sueltan y se unen a etapas).
- Commits: `efdec32` (P-IMP-36), `60c7611` (P-IMP-37), `370f6f5` (P-IMP-38), `a61d292` (fusión de los subagentes y
  `CLAUDE.md`), `08ac225` (P-IMP-39), `027f5e1` (P-IMP-40); P-IMP-41 en el commit siguiente.
- Lista de verificación del responsable (marca bien, mal o duda con nota; se lee con la herramienta ArtifactData):
  https://claude.ai/artifact/H9AbbW2x5qPZ2d35iWyKXd — colección `checks`, documento `notas/general`. Añadir ahí las
  comprobaciones de cada paso nuevo (campos `orden`, `ronda`, `grupo`, `texto`, `como`, `estado`, `nota`).

## Revisión del paso 4

- El verificador revisó `60c7611..370f6f5` y dio el veredicto **«aceptado con reservas»**. Reservas: faltaba la vista
  previa en el diálogo de acciones; el diálogo no avisaba de una variable que no vale; los bloques reescribían algunos
  textos (`NOT ↑a`); X1 ambiguo con etapas «E1» y «1»; sin pantalla no se comprobó el aspecto. El coordinador añadió
  que las constantes 1/0 daban D-TIPO.
- Correcciones aprobadas por el responsable y hechas en P-IMP-39: vista previa «En la norma» en el diálogo de
  acciones; aviso en dos pasos al aceptar una variable que no vale para la acción; aviso cuando X1 puede ser la etapa
  E1 o la 1; constantes 1 y 0 que se escriben, se ven como 1 y 0 y se guardan como true y false (solo como condición completa);
  retardos con paréntesis anidados.
- Opinión del responsable sobre P-IMP-39: «no me disgusta»; pidió categorías en columna como carpetas, la fórmula
  abajo (puede ser larga), «y»/«o» de colores distintos y no encontraba cómo poner acciones. Hecho en P-IMP-40.
- Pendiente: que el responsable pruebe P-IMP-41 con la lista de verificación nueva (ver arriba). Sin pantalla no se han probado el arrastre real ni el aspecto.

## Lista de verificación: notas de la ronda antigua (vaciada el 28-10-2026 a petición del responsable)

El responsable descubrió la lista tarde y pidió empezar de cero. Antes de vaciarla se leyó todo; lo que pedía está en
P-IMP-41. Además dejó anotado:
- Fallaban: arrastrar desde la paleta (causa encontrada y corregida en P-IMP-41) y «el panel izquierdo se estrecha sin
  cortar nada» (P-IMP-38; sin nota; volver a comprobarlo ahora que la receptividad está abajo).
- Petición no relacionada, hecha en P-IMP-41: seleccionar varios elementos con un rectángulo para borrarlos.
- Las dudas sin nota de la ronda del paso 4 eran de comprobaciones viejas, sin sentido ya.
- Forzado: aplazado hasta que el editor tenga jerarquías (decisión del responsable).
- La página de la lista sacaba del cuadro al guardar una nota (se redibujaba entera): corregido el 28-10-2026; por
  eso algunas notas antiguas estaban cortadas.

## Opiniones del responsable sobre el paso 4

- El programador por bloques de P-IMP-38 le parecía «muy infantil». Pidió algo como Scratch, con bloques que encajan
  unos en otros: hecho en P-IMP-39, pendiente de su prueba.
- Las variables internas se llaman **memorias** en la interfaz: hecho en P-IMP-39 (el formato sigue guardando el
  papel `internal`).
- Etiquetas numéricas de etapa, panel izquierdo estrechable y conexiones: conformes.

## Limitaciones conocidas del programador (P-IMP-39)

- Con más de unos 8 niveles apilados a 200 px, el área puede recortar; se usa «⤢ Ampliar».
- El arrastre real con ratón no se prueba sin pantalla: hace falta una prueba manual del responsable.

## Entorno del contenedor en la nube

- PySide6 no viene instalado. Para las pruebas Qt: `pip install PySide6-Essentials` y
  `apt-get install -y libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3`; ejecutar con `QT_QPA_PLATFORM=offscreen`.
- El paquete de especificaciones se busca en `../Definición del proyecto/`. En el contenedor basta un enlace
  simbólico fuera del repositorio: `ln -s "$PWD/docs/definicion_proyecto" "../Definición del proyecto"` (las huellas
  coinciden con `spec/paquete_base.json`).
- `docs/resultados_pruebas.json` registra el sistema donde se ejecutaron las pruebas (aquí, Linux).
