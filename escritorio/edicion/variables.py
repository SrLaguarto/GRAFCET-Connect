"""Nombres, declaraciones e inspección de variables para el editor."""
from __future__ import annotations

import re
from typing import Any
from grafcet.diagnostics import Diagnostic, DiagnosticError
from grafcet.notation import x_etapa
from grafcet.ids import MAX_LABEL, label_key, valid_label
from .constantes import RESERVADAS


class _Variables:
    @staticmethod
    def motivo_nombre(nombre: str) -> str | None:
        """Por qué un nombre no puede ser el de una variable en la interfaz: se confundiría en una fórmula (palabra
        reservada, símbolos, solo cifras o parecido a una duración) o con la actividad de una etapa (X1). None si sirve.
        Un nombre puede llevar espacios **interiores** simples entre palabras («Marcha motor», «Fin de carrera 1»): no
        empieza ni acaba en espacio (quien confirma el nombre lo recorta antes) ni lleva dos espacios seguidos (se rechaza,
        no se reduce, para que lo que se ve sea lo que se guarda). Un nombre que empieza por cifra (1M1, 2S3: nomenclatura
        industrial) vale si lleva alguna letra. En las fórmulas que arman los bloques el núcleo escribe entre comillas
        invertidas (`1M1`, `Marcha motor`) todo nombre que no es una palabra simple, y el resto de la interfaz las oculta
        (P-IMP-46); el usuario no las ve ni las teclea. El núcleo sigue admitiendo cualquier nombre entre comillas
        invertidas, en ficheros antiguos."""
        if nombre.strip().lower() in RESERVADAS:
            return f'"{nombre}" no puede ser nombre de variable: es una palabra de las fórmulas'
        if re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:us|µs|μs|ms|s)", nombre):
            return (f'"{nombre}" no puede ser nombre de variable: se leería como una duración (3s, 500ms…); '
                    "añade alguna letra más, como 1S2")
        if re.fullmatch(r"\d+(?:[.,]\d+)?", nombre):
            return f'"{nombre}" no puede ser nombre de variable: es solo un número; añade alguna letra, como 1M1'
        if nombre != nombre.strip() or "  " in nombre:
            return (f'"{nombre}" no puede ser nombre de variable: lleva espacios al principio o al final, o dos espacios '
                    "seguidos; solo se admite un espacio entre palabras")
        palabras = nombre.split(" ")
        # («+» y «-» se admiten dentro de las palabras, salvo la primera letra del nombre: neumática, «A+», «1V1-14»)
        if not ((re.fullmatch(r"[^\W\d][\w+-]*(?:\.\w+)?", palabras[0])
                 or re.fullmatch(r"\d[\w+-]*", palabras[0]) and re.search(r"[^\W\d_]", nombre))
                and all(re.fullmatch(r"[\w+-]*\w[\w+-]*(?:\.\w+)?", p) for p in palabras[1:])):
            return (f'"{nombre}" no puede ser nombre de variable: debe empezar por una letra o _ (o por una cifra, si lleva '
                    "alguna letra, como 1M1) y no llevar más símbolos que + y -; entre palabras solo un espacio")
        if re.fullmatch(r"X\d+", nombre.replace(" ", "")):
            return (f'"{nombre}" no puede ser nombre de variable: se confundiría con la actividad de la etapa '
                    f'{nombre.replace(" ", "")[1:]}')
        # (el núcleo lee una palabra «X…» como la actividad de una etapa aunque esté entre comillas invertidas)
        if len(palabras) > 1 and any(re.fullmatch(r"X\w+", p) for p in palabras):
            return (f'"{nombre}" no puede ser nombre de variable: una de sus palabras empieza por X y se confundiría con '
                    "la actividad de una etapa (X1…)")
        return None

    def _id_variable(self, nombre: str) -> str | None:
        return next((v["id"] for v in self.ed.model["variables"] if v["name"] == nombre), None) if nombre else None

    def variables(self) -> list[dict[str, Any]]:
        """El diccionario: cada variable con cuántos usos tiene (expresiones y acciones que la escriben)."""
        m = self.ed.model
        return [dict(v, usos=len(self.ed.usages(v["id"])) + sum(a["targetRef"] == v["id"] for a in m["actions"]))
                for v in m["variables"]]

    def nueva_variable(self, nombre: str, papel: str = "input", tipo: dict[str, Any] | None = None) -> str | None:
        """Crea una variable (una operación de deshacer); devuelve el motivo si el nombre no es válido o está repetido. Los
        espacios del principio y del final del nombre se recortan."""
        nombre = nombre.strip()

        def hacer() -> None:
            motivo = self.motivo_nombre(nombre) if nombre.strip() else None
            if motivo:
                raise DiagnosticError(Diagnostic("D-FORMATO", motivo))
            if not valid_label(nombre):  # como al renombrar
                raise DiagnosticError(Diagnostic("D-FORMATO", f"nombre inválido: de 1 a {MAX_LABEL} caracteres"))
            self.ed.add_variable(nombre, papel, tipo or {"kind": "bool"})
        return self._atomico("crear variable", hacer)

    def motivo_variable_nueva(self, nombre: str) -> str | None:
        """Por qué `nombre` no puede ser el de una variable nueva (no válido o ya existe); None si sirve. Se juzga el nombre
        recortado (`nuevas_variables` y la tabla lo crean con él)."""
        nombre = nombre.strip()
        if not nombre:
            return "Falta el nombre."
        motivo = self.motivo_nombre(nombre)
        if motivo:
            return motivo
        if not valid_label(nombre):
            return f"nombre inválido: de 1 a {MAX_LABEL} caracteres"
        if any(label_key(v["name"]) == label_key(nombre) for v in self.ed.model["variables"]):
            return f"variable «{nombre}» ya existe en el ámbito"
        return None

    def nuevas_variables(self, filas: list[tuple[str, str, dict[str, Any]]]) -> list[str | None]:
        """Crea varias variables (nombre, papel, tipo) como una sola operación de deshacer (pegar desde una hoja de cálculo). Las que no
        sirven (nombre no válido o repetido, también entre ellas) no se crean; devuelve, por fila, su motivo o None si se creó."""
        motivos: list[str | None] = [None] * len(filas)

        def hacer() -> None:
            for i, (nombre, papel, tipo) in enumerate(filas):
                nombre = nombre.strip()
                motivos[i] = self.motivo_variable_nueva(nombre)
                if motivos[i] is None:
                    self.ed.add_variable(nombre, papel, dict(tipo))
        motivo = self._atomico("pegar variables", hacer)
        return motivos if motivo is None else [motivo] * len(filas)

    def cambiar_variable(self, vid: str, nombre: str | None = None, **cambios: Any) -> str | None:
        """Cambia nombre (y el texto de sus usos), papel, tipo, unidad o valor inicial, en una sola operación."""
        v = next(x for x in self.ed.model["variables"] if x["id"] == vid)
        nombre = nombre.strip() if nombre is not None else None

        def hacer() -> None:
            if nombre is not None and nombre != v["name"]:
                motivo = self.motivo_nombre(nombre) if nombre.strip() else None
                if motivo:
                    raise DiagnosticError(Diagnostic("D-FORMATO", motivo))
                self.ed.rename(vid, nombre)
            if cambios:
                self.ed.change_variable(vid, **cambios)
        return self._atomico("cambiar variable", hacer)

    def quitar_variable(self, vid: str) -> str | None:
        return self._atomico("quitar variable", lambda: self.ed.delete_variable(vid))

    def fuente_bloques(self) -> tuple[dict[str, tuple[str, str]], list[str]]:
        """Lo que ofrece el programador por bloques: variables {nombre: (papel, tipo)} y etapas en notación X."""
        m = self.ed.model
        return ({v["name"]: (v["role"], v["type"]["kind"]) for v in m["variables"]}, [x_etapa(s["label"]) for s in m["steps"]])
