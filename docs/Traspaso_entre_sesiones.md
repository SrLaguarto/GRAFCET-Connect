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

## Revisión del paso 4: RECHAZADO (sin corregir todavía)

El verificador se lanzó a mano en la sesión anterior: un agente aparte con las instrucciones de
`.claude/agents/verificador.md` y Sonnet, porque los subagentes llegaron con la sesión ya abierta. Revisó
`60c7611..370f6f5`. Las 194 pruebas pasan, pero rechazó el paso por tres fallos reproducibles, que el coordinador
confirmó. **No se ha corregido nada: el responsable decide si lo corrige el implementador.**

Bloqueantes:

- **H1.** Una variable de tipo Duración rompe el panel de variables. El fallo está en `escritorio/variables.py:103`
  (`KeyError: 'scale'` al buscar su tipo). Después la tabla deja de aceptar cambios y la ventana no refresca los
  diagnósticos ni deshacer y rehacer. Además, un decimal de escala 0 o mayor que 3 se muestra como «Booleana».
- **H2.** El cajón «Constantes» inserta `1` y `0`, que el analizador lee como enteros: la transición no compila
  (D-TIPO), aunque el panel diga «correcta». `true` y `false` sí compilan. Hay que decidir si `1` y `0` se traducen
  a booleanos en la notación del usuario o si el cajón inserta `true` y `false`.
- **H3.** `Edicion._atomico` (`escritorio/edicion.py`) deja basura en la pila de rehacer si falla a mitad y antes
  había algo que rehacer: «rehacer» vuelve a aplicar lo que había fallado. Pasa en el diálogo de acción al crear una
  variable con una condición mal escrita, y también en `cambiar_variable`.

Observaciones:

- **H4.** «Temporizar…» sobre una comparación o sobre varios bloques no pone paréntesis y cambia el significado.
  Por ejemplo, `3s/CT >= 3` es `delay(CT) >= 3`.
- **H5.** Algunas operaciones de bloques dejan secuencias inválidas: «( )» con el cursor delante de un bloque, o
  NOT/↑ sobre una selección que empieza o acaba en `·`.
- **H6.** Las etiquetas numéricas chocan con las E0..En de los ejemplos y de los proyectos antiguos: existen a la
  vez «0» y «E0»; `X0` va siempre a E0, y el cajón ofrece X1 dos veces.
- **H7.** `update_action` pierde `limitUs` de una acción continua limitada.
- **H8.** El panel acepta valores iniciales mal escritos («abc», «1,5») sin avisar. Después la simulación se
  bloquea por D-FORMATO.
- **H9.** Con una acción señalada, Supr borra la etapa entera. Se pide confirmación, pero se espera que borre solo
  la acción.
- **H10.** Algunos textos raros se reescriben al pasar por bloques: `NOT NOT a/2s` cambia de significado, y
  `↑a/3s` pasa a `↑(a/3s)`.
- **H11.** Menores:
  - Los nombres con espacios no se citan.
  - `_insertar` y `_prefijar` quedan como código muerto.
  - La nota de REQ-EDT-02 en `spec/clasificacion.py` dice todavía «panel de acciones pendiente».
  - El docstring de S-EDI41 no coincide con el texto guardado.
  - Faltan pruebas para H1 a H5 y para la ambigüedad de X1.

Dudas que decide el responsable:

1. ¿Reordenar acciones debe contar como edición del modelo (cambia `revisionId`) o solo del dibujo?
2. ¿«Siempre verdadera»: `1` traducido a booleano, o el cajón inserta `true` (H2)?
3. ¿Cuando existen la etapa «1» y la etapa «E1», a cuál se refiere X1 (H6)? Hoy gana E1.
4. ¿Los bloques pueden reescribir un texto escrito a mano que no compila (`↑a/3s`), o deben dejarlo intacto?

El programador por bloques se va a sustituir por uno tipo Scratch, así que H4, H5 y H10 conviene resolverlos en el
programador nuevo, no en `escritorio/bloques.py` actual.

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
