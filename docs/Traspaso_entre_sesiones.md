# Traspaso entre sesiones

Nota para la siguiente conversación de Claude Code (coordinador). Estado al 28-10-2026.

## Dónde está el trabajo

- Rama: `claude/awesome-mendel-kld8yv` (no está fusionada en `main`). La siguiente sesión parte de ella.
- Pasos 1 a 4 de `docs/Plan_de_trabajo_Sonnet.md` hechos. Últimas decisiones: P-IMP-36 (tramos verticales mínimos,
  transición que se agarra sin sacar rama), P-IMP-37 (sin escalones, una flecha por lazo, imán, panel izquierdo
  plegable, arrastre visible desde la paleta) y P-IMP-38 (paso 4: variables, acciones de etapa y un primer
  programador por bloques).
- Commits: `efdec32` (P-IMP-36), `60c7611` (P-IMP-37), `370f6f5` (P-IMP-38), `a61d292` (fusión de los subagentes y
  `CLAUDE.md`).
- Lista de verificación del responsable (marca bien, mal o duda con nota; se lee con la herramienta ArtifactData):
  https://claude.ai/artifact/H9AbbW2x5qPZ2d35iWyKXd — colección `checks`, documento `notas/general`. Añadir ahí las
  comprobaciones de cada paso nuevo (campos `orden`, `ronda`, `grupo`, `texto`, `como`, `estado`, `nota`).

## Revisión pendiente del paso 4

El verificador (lanzado a mano en la sesión anterior, porque los subagentes llegaron con la sesión ya abierta) estaba
revisando `60c7611..370f6f5`. Si su veredicto no figura más abajo, pedir una revisión nueva al `verificador` antes de
seguir, y contar el resultado al responsable sin corregir nada hasta que lo apruebe.

## Opiniones del responsable sobre el paso 4

- El programador por bloques actual (fila de fichas de colores en `escritorio/bloques.py`) le parece «muy infantil»:
  quiere algo como Scratch, con bloques que encajan unos en otros (ver la orden de la siguiente sesión).
- Las variables internas se llamarán **memorias** en la interfaz.
- Etiquetas numéricas de etapa, panel izquierdo estrechable y conexiones: conformes.

## Entorno del contenedor en la nube

- PySide6 no viene instalado. Para las pruebas Qt: `pip install PySide6-Essentials` y
  `apt-get install -y libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3`; ejecutar con `QT_QPA_PLATFORM=offscreen`.
- El paquete de especificaciones se busca en `../Definición del proyecto/`. En el contenedor basta un enlace
  simbólico fuera del repositorio: `ln -s "$PWD/docs/definicion_proyecto" "../Definición del proyecto"` (las huellas
  coinciden con `spec/paquete_base.json`).
- `docs/resultados_pruebas.json` registra el sistema donde se ejecutaron las pruebas (aquí, Linux).
