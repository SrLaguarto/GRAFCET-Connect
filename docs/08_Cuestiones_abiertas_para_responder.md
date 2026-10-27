# Cuestiones abiertas para responder

Hoja de trabajo · 25-10-2026 · Responsable: SrLaguarto

## Cómo rellenarla

> **Más cómodo: el comparador.** «Comparar decisiones.bat» abre cada cuestión con su ejemplo ejecutándose una vez por cada opción, lado a lado; se elige con un botón y la respuesta se guarda en `docs/decisiones.json` (P-IMP-21). Esta hoja sigue valiendo para citar cláusulas y para el bloque 9.

1. Marca **una** opción con una X: `[X]`. Si ninguna te convence, marca **Otra** y escríbela.
2. Si consultas la norma, apunta la **cláusula y la página** que lo respaldan, y si el texto es **normativo** o solo una **nota/ejemplo**. Una nota o un ejemplo no obligan; esto es lo que pide U-01.
3. Si no lo tienes claro, marca **Dejar abierta**: el programa seguirá deteniéndose en ese caso y no se inventa nada.
4. Guarda el archivo y avísame. Yo implemento cada respuesta con su prueba y su commit, y cito esta hoja.

Las páginas son del PDF local («Resumen de norma UNE Grafcet.pdf»), según el mapa del documento 02. Los ejemplos usan la notación del banco de pruebas: `↑p` es una subida de p, `3s/X1` es «3 s después de activarse la etapa 1», y `n := n + 1 (al activar)` es una acción memorizada.

## Índice por prioridad

| Bloque | Qué bloquea hoy | Preguntas |
|---|---|---|
| 1. Inicialización (U-09) | Muchos programas normales no arrancan | 1.1–1.5 |
| 2. Lecturas y escrituras en el mismo instante (U-05) | Contadores y asignaciones encadenadas | 2.1–2.5 |
| 3. Etapa activada y desactivada a la vez (U-04) | Acciones y temporizadores de esa etapa | 3.1–3.4 |
| 4. Fronteras de tiempo (U-06) | Temporizadores en casos límite | 4.1–4.5 |
| 5. Flancos durante el recorrido (U-03) | Ya es opción; falta la parte de acciones | 5.1–5.3 |
| 6. Transiciones fuente y arranque vacío (U-07) | Modelos sin etapa inicial o con fuentes | 6.1–6.4 |
| 7. Jerarquías: forzado, macroetapas y encapsulación (U-08, U-02) | Su ejecución | 7.1–7.7 |
| 8. Otras dudas mías (H-08, H-10) | Casos poco frecuentes | 8.1–8.2 |
| 9. Decisiones de producto (U-10, U-11, U-12 y P-IMP) | Plataformas, formato y alcance | 9.1–9.5 |

---

## 1. Inicialización (U-09)

**Dónde mirar:** §4.5.2 (PDF 11–12), §4.8.3 (PDF 12–14), tabla 1 [3] (PDF 18–21), tabla 10 [5] y [41] (PDF 43–46), tabla 11 [42] (PDF 47–48).

### 1.1 · Acción «al activar» en una etapa inicial
**Hoy:** el programa no arranca (D-SEM-PENDIENTE U-09).
**Ejemplo:** E0 es inicial y tiene `n := 1 (al activar)`. La variable n empieza en 0.
**Pregunta:** al arrancar, ¿se ejecuta esa acción?
- [X] **A.** Sí: arrancar cuenta como activar E0. Resultado: n = 1.
- [ ] **B.** No: la situación inicial no es una activación. Resultado: n = 0.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01).

Comentario:

### 1.2 · Situación inicial inestable
**Hoy:** el programa no arranca.
**Ejemplo:** E0 inicial; t1: E0 → E1 con receptividad `= 1` (siempre verdadera), o con `p` cuando p ya vale 1 al arrancar.
**Pregunta:** ¿qué pasa en el instante 0?
- [X] **A.** Evoluciona en ese mismo instante: E0 queda como etapa virtual (sin pulsos en sus salidas continuas) y se arranca en E1.
- [ ] **B.** Se arranca en E0 y no evoluciona hasta el primer cambio de una entrada.
- [ ] **C.** Es un error de diseño: el programa no compila.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01).

Comentario:

### 1.3 · Temporizador sobre una entrada que ya es verdadera al arrancar
**Hoy:** el programa no arranca.
**Ejemplo:** E0 inicial; t1: E0 → E1 con `3s/p`, y p vale 1 desde el arranque.
**Pregunta:** ¿cuándo franquea t1?
- [X] **A.** A los 3 s: cuenta desde el arranque.
- [ ] **B.** Nunca, mientras p no baje y vuelva a subir: hace falta una subida real de p.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01).

Comentario:

### 1.4 · Duración de una etapa inicial (confirmar lo implementado, H-02)
**Hoy:** cuenta desde el arranque, como dicen los oráculos T-12a y T-12c.
**Ejemplo:** E0 inicial; t1: E0 → E1 con `3s/X0`.
**Pregunta:** ¿franquea t1 a los 3 s del arranque?
- [X] **A.** Sí, como está ahora.
- [ ] **B.** No:
- [ ] **Dejar abierta** (pasaría a detenerse)

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01).

### 1.5 · Variable memorizada con valor inicial distinto de cero (H-07)
**Hoy:** el programa no arranca. El resumen local (§4.8.3) dice que las memorizadas empiezan en falso/0.
**Ejemplo:** la variable interna n se declara con valor inicial 5.
**Pregunta:** ¿se admite?
- [X] **A.** No: siempre empieza en 0. Declarar otro valor es un error de compilación. Comentario del responsable (27-10-2026): en la aplicación no se podrá declarar un valor fuera del grafcet; debe ponerse con una acción (n := 5).
- [ ] **B.** Sí: empieza con el valor declarado.
- [ ] **C.** Solo como «intervención de depuración» marcada, no en una ejecución normal.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01). Nota: Las memorizadas empiezan en 0. Si se quiere otro valor inicial, se pone con una acción «al activar» en la etapa inicial (por ejemplo n := 5 en E0), que se ejecuta al arrancar por la respuesta 1.1.

---

## 2. Lecturas y escrituras en el mismo instante (U-05)

**Dónde mirar:** §4.8.3, §4.9.5, §4.10.5 y su nota 3 (PDF 12–17).

### 2.1 · Dos incrementos simultáneos
**Hoy:** se detiene (D-SEM-PENDIENTE U-05).
**Ejemplo:** t: A → {B, C}. B tiene `n := n + 1 (al activar)` y C también. n = 0 antes.
**Pregunta:** ¿cuánto vale n después?
- [ ] **A.** 1: las dos leen el valor anterior (0) y escriben lo mismo.
- [ ] **B.** 2: los incrementos se acumulan.
- [X] **C.** Error: conflicto de escritura, no compila.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01). Nota: Dar conflicto si las dos se activan a la vez.

### 2.2 · Intercambio de valores
**Hoy:** se detiene.
**Ejemplo:** al activarse B se ejecutan `x := y` e `y := x` a la vez, con x = 2 e y = 5.
**Pregunta:** ¿resultado?
- [ ] **A.** x = 5, y = 2: ambas leen el estado anterior y se intercambian.
- [X] **B.** Error: dependencia cruzada no permitida, no compila.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01).

### 2.3 · Receptividad que lee un valor recién asignado en el mismo instante
**Hoy:** se detiene.
**Ejemplo:** n = 0. Se franquea A → B; B tiene `n := 1 (al activar)`; la transición B → C tiene `[n = 1]`.
**Pregunta:** ¿pasa a C en ese mismo instante?
- [X] **A.** Sí: la receptividad ve n = 1 y B queda como etapa virtual.
- [ ] **B.** No en ese instante: ve n = 0 y se queda en B (pasaría a C en el siguiente cambio de entradas).
- [ ] **C.** Error: no compila.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01). Nota: Realmente no es virtual, ya que cambia un valor. En la norma es una «etapa inestable»: sus acciones memorizadas se ejecutan y solo las continuas no producen salida.

### 2.4 · Dos asignaciones distintas sucesivas en el mismo instante
**Hoy:** se detiene (si los valores son iguales, se acepta).
**Ejemplo:** B tiene `z := 1 (al activar)`, la transición B → C tiene `= 1` y C tiene `z := 2 (al activar)`. Se recorre A → B → C en un instante.
**Pregunta:** ¿cuánto vale z?
- [X] **A.** 2: vale la última del recorrido.
- [ ] **B.** Error: conflicto de escritura.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01).

### 2.5 · Salida continua que lee una memoria cambiada en ese instante (confirmar lo implementado)
**Hoy:** la salida usa el valor final del instante (lectura L-01).
**Ejemplo:** `alarma si [n ≥ 3]` en la etapa A. Una subida de «pulso» lleva n de 2 a 3.
**Pregunta:** ¿se enciende la alarma en ese mismo instante?
- [X] **A.** Sí, como está ahora.
- [ ] **B.** No, en el instante siguiente.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 25-10-2026 (sin cláusula citada; contraste normativo pendiente, U-01).

---

## 3. Etapa activada y desactivada a la vez (U-04)

**Dónde mirar:** §4.5.6, §4.7 y §4.9 (PDF 12–17). La regla 5 dice que la etapa sigue activa; la duda es qué pasa con sus acciones y sus temporizadores.

### 3.1 · Acciones de una etapa en permanencia activa
**Hoy:** se detiene (D-SEM-PENDIENTE U-04).
**Ejemplo:** A y B activas; t: A → B y u: B → C, ambas con p, franquean a la vez. B tiene `n := n + 1 (al activar)` y `m := m + 1 (al desactivar)`. B sigue activa.
**Pregunta:**
- [X] **A.** No se ejecuta ninguna: B no ha cambiado de estado.
- [ ] **B.** Se ejecutan las dos: B «sale y entra» a efectos de acciones.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 3.2 · Temporizador de una etapa en permanencia activa
**Hoy:** se detiene.
**Ejemplo:** el mismo caso, con `5s/XB` contando desde hace 2 s.
**Pregunta:**
- [X] **A.** Sigue contando: vence 3 s después. Es coherente con tu decisión P-IMP-18.
- [ ] **B.** Vuelve a empezar: vence 5 s después.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 3.3 · Activar una etapa que ya estaba activa (H-05)
**Hoy:** se detiene.
**Ejemplo:** A y B activas; t: A → B franquea (B no es precedente de t). B tiene `n := n + 1 (al activar)`.
**Pregunta:**
- [X] **A.** No se ejecuta: B ya estaba activa.
- [ ] **B.** Se ejecuta: hay una activación de B.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 3.4 · Etapa encapsulante en permanencia activa
**Hoy:** la encapsulación aún no se ejecuta.
**Pregunta:** si la encapsulante H se activa y se desactiva a la vez, ¿su contenido…
- [X] **A.** …se mantiene como estaba?
- [ ] **B.** …se reinicia con sus etapas de activación?
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

---

## 4. Fronteras de tiempo (U-06)

**Dónde mirar:** tabla 4 [17] y [18] (PDF 22–25); tabla 5 [23] a [25] (PDF 26–33).

### 4.1 · La entrada cae exactamente al vencer el retardo
**Hoy:** se detiene.
**Ejemplo:** t: A → B con `2s/p`. p sube a 0 s y baja exactamente a 2 s.
- [X] **A.** Franquea: el vencimiento llega antes que la caída.
- [ ] **B.** No franquea: la caída cancela el retardo.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 4.2 · Rebote durante el retardo de desconexión
**Hoy:** se detiene.
**Ejemplo:** `1s/p/2s`. p sube a 0 s (la condición pasa a verdadera a 1 s), baja a 3 s (seguiría verdadera hasta 5 s) y vuelve a subir a 4 s.
- [X] **A.** La condición sigue verdadera sin interrupción: la nueva subida anula la desconexión pendiente.
- [ ] **B.** Se mantiene el plazo de 5 s; luego hace falta 1 s de p para volver a ser verdadera.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 4.3 · Cambio de entrada y vencimiento en el mismo instante, sin relación entre ellos
**Hoy:** se detiene siempre (H-17).
**Ejemplo:** un temporizador de una rama vence a 2 s y, también a 2 s, cambia una entrada que solo usa otra rama.
- [X] **A.** Se procesan juntos, como un solo instante.
- [ ] **B.** Primero el vencimiento y luego la entrada.
- [ ] **C.** Primero la entrada y luego el vencimiento.
- [ ] **D.** Solo se detiene si los resultados de A, B y C difieren.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 4.4 · Retardo cero
**Hoy:** `0s/p` no compila.
- [ ] **A.** `0s/p` equivale a `p`.
- [X] **B.** Se prohíbe: no compila.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 4.5 · Duración T de una etapa inactiva
**Hoy:** `elapsed(etapa)` no se puede ejecutar.
- [X] **A.** Vale 0.
- [ ] **B.** No tiene valor: leerla con la etapa inactiva es un error.
- [ ] **C.** Conserva la última duración.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

---

## 5. Flancos durante el recorrido (U-03)

**Dónde mirar:** §4.6, §4.7 y §4.9; tabla 4 [15] y [16]; tabla 6 [29] (PDF 12–17 y 22–33).

### 5.1 · Lectura por defecto en el programa final
**Hoy:** se puede elegir (P-IMP-15) y por defecto se detiene. Recuerda el hallazgo H-23: con «recorrido», un modelo con retorno puede girar sin fin.
- [ ] **A.** Por defecto «detener».
- [X] **B.** Por defecto «situación anterior»: el flanco solo vale para las transiciones validadas antes de él.
- [ ] **C.** Por defecto «recorrido».

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 5.2 · Acción por evento en una etapa que se desactiva con ese mismo evento
**Hoy:** se detiene.
**Ejemplo:** A tiene `H := 0 por ↑a`, y t: A → B con `↑a`.
- [ ] **A.** Se ejecuta: A estaba activa cuando ocurrió el evento.
- [X] **B.** No se ejecuta.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 5.3 · Acción por evento en una etapa que se activa con ese mismo evento
**Hoy:** se detiene.
**Ejemplo:** B tiene `H := 0 por ↑a`, y t: A → B con `↑a`.
- [X] **A.** No se ejecuta: B no estaba activa al ocurrir el evento.
- [ ] **B.** Se ejecuta.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

---

## 6. Transiciones fuente y arranque vacío (U-07)

**Dónde mirar:** §6.3 (PDF 33–39).

### 6.1 · Grafcet sin etapas iniciales
**Hoy:** no arranca.
- [X] **A.** Error: no compila.
- [ ] **B.** Arranca sin etapas activas (solo se activará mediante transiciones fuente).
- [ ] **C.** Arranca con una advertencia.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 6.2 · Transición fuente con receptividad de nivel
**Hoy:** no compila.
**Ejemplo:** una transición sin etapa anterior y con receptividad `p`, que lleva a A.
- [X] **A.** No se permite: no compila.
- [ ] **B.** Mientras p = 1, A se mantiene activa (imposición continua).
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 6.3 · Transición fuente con flanco
**Comentario del responsable:** si no se admitieran transiciones fuente, no se ejecutaría y daría error; como se admiten, una vez por flanco, en la línea de las anteriores («situación anterior»).
**Hoy:** franquea una vez con el evento, pero se detiene si en el mismo instante seguiría validada.
**Ejemplo:** una transición sin etapa anterior con `↑p`, que lleva a A.
- [X] **A.** Franquea exactamente una vez por cada subida de p.
- [ ] **Dejar abierta**
- [ ] **Otra:**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

### 6.4 · Transición sin etapas antes ni después
**Hoy:** se guarda como borrador, pero no compila.
- [X] **A.** No se permite.
- [ ] **B.** Se permite, sin efecto.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?: Respondida por el responsable el 27-10-2026 en el comparador (sin cláusula citada; contraste normativo pendiente, U-01).

---

## 7. Jerarquías: forzado, macroetapas y encapsulación (U-08, U-02)

**Dónde mirar:** §7.2 a §7.5 y tablas 8 a 11 (PDF 40–48).

> Desde P-IMP-23 las jerarquías se ejecutan y cada cuestión de este bloque tiene su ejemplo en el comparador.

### 7.1 · Quién fuerza a quién (U-02)
La frase del §7.3 sobre el sentido jerárquico parece invertir sujeto y objeto.
- [ ] **A.** La etapa de un parcial **superior** fuerza a un parcial **inferior**.
- [ ] **B.** Es al revés.
- [ ] **Dejar abierta**

Cláusula / página:

### 7.2 · Cuándo se aplica el forzado (H-18)
**Ejemplo:** la etapa F (que fuerza G = {B}) se activa en una evolución en la que G también podría evolucionar.
- [ ] **A.** El forzado se aplica en esa misma evolución y gana a la evolución normal de G.
- [ ] **B.** G evoluciona normalmente en esa evolución y el forzado se aplica en la siguiente.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?:

### 7.3 · Temporizadores de un parcial forzado
- [ ] **A.** Siguen contando.
- [ ] **B.** Se congelan mientras dura el forzado.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?:

### 7.4 · Forzar un recinto cuya encapsulante está inactiva
- [ ] **A.** Error de diseño: no compila.
- [ ] **B.** Se fuerza igualmente.
- [ ] **C.** El forzado se ignora mientras la encapsulante esté inactiva.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?:

### 7.5 · Salir de una macroetapa con ramas internas aún activas
- [ ] **A.** Al salir se desactivan todas las etapas de la expansión.
- [ ] **B.** Las ramas siguen activas.
- [ ] **C.** Error de diseño.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?:

### 7.6 · Desactivar la encapsulante en el mismo instante en que vence un temporizador interno
- [ ] **A.** Gana la desactivación: el temporizador interno no tiene efecto.
- [ ] **B.** Primero actúa el temporizador interno y luego se desactiva.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?:

### 7.8 · Acciones de las etapas que cambia un forzado (H-24, nueva)
**Ejemplo:** H fuerza G = {B}; B tiene `n := 1 (al activar)`.
- [ ] **A.** Se ejecutan: es una activación.
- [ ] **B.** No se ejecutan: el forzado impone la situación sin acciones.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?:

### 7.7 · Etapas iniciales dentro de la expansión de una macroetapa
- [ ] **A.** Se permiten: están activas al arrancar.
- [ ] **B.** No se permiten.
- [ ] **Dejar abierta**

Cláusula / página / ¿normativo o nota?:

---

## 8. Otras dudas mías

### 8.1 · Actividad de un parcial con parciales hijos (H-08)
- [ ] **A.** Cuenta también las etapas de los parciales hijos.
- [ ] **B.** Solo las etapas propias.
- [ ] **Dejar abierta**

### 8.2 · Receptividad que lee una salida continua durante un recorrido (H-10)
**Ejemplo:** B tiene `y` continua; la transición B → C tiene `y`; B es virtual.
- [ ] **A.** Se prohíbe leer salidas continuas en receptividades.
- [ ] **B.** Se lee el valor de la situación anterior.
- [ ] **C.** Se lee el valor según la situación virtual.
- [ ] **Dejar abierta**

---

## 9. Decisiones de producto (no hace falta la norma)

### 9.1 · Sistemas en los que debe funcionar (U-10)
- [ ] Windows 11 (64 bits)
- [ ] Windows 10 (64 bits)
- [ ] macOS (versión:          )
- [ ] Linux (distribución:          )

Equipo de referencia para medir el rendimiento (procesador, RAM):

### 9.2 · Formato de archivo 0.1 (U-11)
- [ ] **A.** Lo apruebo como base.
- [ ] **B.** Quiero revisarlo antes. Qué cambiar:

### 9.3 · Alcance aprobado para seguir (U-12)
La propuesta está en `docs/02_Alcance_implementable.md`.
- [ ] **A.** Apruebo la propuesta tal cual.
- [ ] **B.** La apruebo con cambios:

### 9.4 · Decisiones de implementación P-IMP-01 a P-IMP-14
El detalle está en `docs/04_Decisiones_de_implementacion.md`. Las P-IMP-15 a 18 ya las decidiste tú.

| ID | Resumen | Acepto | Cambiar (cómo) |
|---|---|---|---|
| P-IMP-01 | Códigos de diagnóstico nuevos (D-ALTERNANCIA, D-NOMBRE-COLISION, D-JERARQUIA-INICIAL, D-ENTRADA-SIN-VALOR, D-CAPACIDAD-NO-SOPORTADA) | [ ] | |
| P-IMP-02 | El valor inicial de las entradas lo da el escenario | [ ] | |
| P-IMP-03 | Ficheros «familia-hexadecimal.json»; IDs de documento cortos | [ ] | |
| P-IMP-04 | Renombrar no cambia la revisión del modelo | [ ] | |
| P-IMP-05 | Las conexiones etapa→etapa se guardan como borrador con error | [ ] | |
| P-IMP-06 | Sintaxis de texto: `2 s`, nombres entre acentos graves, `G.A`, sin mezclar entero y decimal | [ ] | |
| P-IMP-07 | Versión menor, identificador de revisión, traza por líneas, guardado con diario | [ ] | |
| P-IMP-08 | Deshacer y rehacer guardando copias; la vista no copia el modelo | [ ] | |
| P-IMP-09 | Límites internos (profundidad, lotes, vencimientos simultáneos) | [ ] | |
| P-IMP-10 | Una entrada manual se aplica en el instante actual | [ ] | |
| P-IMP-11 | «Estado declarado» solo para pruebas | [ ] | |
| P-IMP-12 | Duraciones no negativas; coordenadas con 3 decimales | [ ] | |
| P-IMP-13 | Acciones al activar o desactivar sin condición adicional | [ ] | |
| P-IMP-14 | Campo `limitUs` para las acciones limitadas | [ ] | |

### 9.5 · Programa de escritorio
- [ ] **A.** Permiso para instalar PySide6 y PyInstaller desde PyPI y empezar el programa con su `.exe` portable.
- [ ] **B.** Todavía no.

---

Comentarios generales:
