"""Propuestas de nombres y selección de señales para traer E/S."""
from dataclasses import dataclass
import re

from conexion.uniones import TIPOS, Union
from grafcet.ids import label_key


from conexion.catalogo_directo import interna, nombre_visible, de_fabrica


def proponer(nombre):
    nombre = nombre.replace("&", "y")
    nombre = re.sub(r"\s*\(([+-])\)", r"\1", nombre)
    nombre = nombre.replace("(", " ").replace(")", " ")
    return " ".join(nombre.split())


@dataclass
class Fila:
    senal: dict
    nombre: str
    marcada: bool
    ya: str = ""
    cambiado: bool = False
    motivo: str = ""
    existente: str = ""


class Propuestas:
    def __init__(self, edicion, config, catalogo):
        self.edicion = edicion
        self.config = config
        self.avisos = []
        variables = {v["id"]: v for v in edicion.ed.model["variables"]}
        unidas = {u.id: variables.get(u.variable) for u in config.uniones}
        self.filas = []
        from conexion.filtro_directo import excluida
        for senal in catalogo:
            if excluida(config, senal):
                continue
            if senal["name"].strip() in ("", "-"):
                continue
            variable = unidas.get(senal["id"])
            ya = variable["name"] if variable else ""
            nombre = ya or proponer(nombre_visible(senal))
            marcada = not bool(ya)
            self.filas.append(Fila(senal, nombre, marcada, ya))
        self.validar()

    def validar(self):
        variables = self.edicion.ed.model["variables"]
        por_nombre = {label_key(v["name"]): v for v in variables}
        unidas = {u.variable for u in self.config.uniones}
        seleccionadas = [label_key(f.nombre) for f in self.filas if f.marcada and not f.ya]
        for fila in self.filas:
            fila.motivo = ""
            fila.existente = ""
            if fila.ya:
                continue
            variable = por_nombre.get(label_key(fila.nombre))
            if variable:
                papel = fila.senal["kind"].lower()
                tipo = TIPOS[fila.senal["type"].lower()]
                if variable["role"] != papel or variable["type"]["kind"] != tipo or variable["id"] in unidas:
                    roles = {"input": "entrada", "output": "salida", "internal": "memoria"}
                    rol = roles.get(variable["role"], "otro papel")
                    fila.motivo = f"Ya hay una variable con ese nombre ({rol}, {variable['type']['kind']})"
                else:
                    fila.existente = variable["id"]
            else:
                fila.motivo = self.edicion.motivo_variable_nueva(fila.nombre) or ""
            if fila.marcada and seleccionadas.count(label_key(fila.nombre)) > 1:
                fila.motivo = "Hay varias señales seleccionadas con el mismo nombre de variable"

    def elegidas(self):
        return [f for f in self.filas if f.marcada and not f.ya]

    def pendientes(self):
        return sum(bool(f.motivo) for f in self.elegidas())


class HistorialUniones:
    """Las uniones acompañan al asiento de deshacer del editor, sin modificar el núcleo."""
    def __init__(self):
        self.operaciones = []

    def registrar(self, editor, asiento, antes, despues):
        self.operaciones.append([editor, asiento, antes, despues, True])

    def sincronizar(self, editor, config):
        operaciones = [o for o in self.operaciones if o[0] is editor]
        cambio = False
        for operacion in operaciones:
            origen, asiento, antes, despues, aplicada = operacion
            ahora = any(x[1] is asiento[1] and x[2] is asiento[2] for x in editor.undo_stack)
            deshecha = any(x[1] is asiento[1] and x[2] is asiento[2] for x in editor.redo_stack)
            if (ahora or deshecha) and ahora != aplicada:
                operacion[4] = ahora
                cambio = True
        if cambio:
            from copy import deepcopy
            aplicadas = [o for o in operaciones if o[4]]
            config.uniones = deepcopy(aplicadas[-1][3] if aplicadas else operaciones[0][2])


def traer(propuestas, historial):
    from copy import deepcopy
    propuestas.validar()
    if propuestas.pendientes():
        raise ValueError("Hay nombres por corregir")
    filas = propuestas.elegidas()
    if not filas:
        return f"0 creadas, 0 unidas a variables existentes, {len(propuestas.avisos)} avisos"
    edicion = propuestas.edicion
    editor = edicion.ed
    antes = deepcopy(propuestas.config.uniones)
    from .variables import TIPOS as TIPOS_VARIABLES
    tipos_variables = {tipo["kind"]: tipo for tipo, etiqueta in TIPOS_VARIABLES}
    nuevas = [(f.nombre, f.senal["kind"].lower(), dict(tipos_variables[TIPOS[f.senal["type"].lower()]]))
              for f in filas if not f.existente]
    if nuevas:
        motivos = edicion.nuevas_variables(nuevas)
        if any(motivos):
            raise ValueError("; ".join(m for m in motivos if m))
    else:
        editor._txn("Traer E/S", lambda modelo, presentacion: None, view_only=True)
    variables = {label_key(v["name"]): v for v in editor.model["variables"]}
    uniones = [Union(variables[label_key(f.nombre)]["id"], f.senal["id"], f.senal["name"],
                     f.senal["type"], f.senal["kind"].lower()) for f in filas]
    propuestas.config.uniones.extend(uniones)
    asiento = editor.undo_stack[-1]
    historial.registrar(editor, asiento, antes, deepcopy(propuestas.config.uniones))
    existentes = sum(bool(f.existente) for f in filas)
    return f"{len(nuevas)} creadas, {existentes} unidas a variables existentes, {len(propuestas.avisos)} avisos"
