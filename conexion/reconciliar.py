"""Relectura de identidades: nunca cambia variables ni el GRAFCET."""


def reconciliar(config, documento, catalogo):
    variables = {v["id"]: v for v in documento["variables"]}
    por_id = {s["id"]: s for s in catalogo}
    ocupadas = {u.id for u in config.uniones}
    avisos = []
    for union in config.uniones:
        union.motivo = ""
        variable = variables.get(union.variable)
        if not union.compatible(variable):
            union.motivo = "El papel o el tipo de la variable ha cambiado" if variable else "Variable no encontrada"
        senal = por_id.get(union.id)
        if senal is None and not union.motivo:
            candidatas = [s for s in catalogo if s["name"] == union.nombre
                          and s["type"].lower() == union.tipo.lower() and s["kind"].lower() == union.papel]
            if len(candidatas) == 1 and candidatas[0]["id"] not in ocupadas:
                ocupadas.discard(union.id)
                union.id = candidatas[0]["id"]
                ocupadas.add(union.id)
                senal = candidatas[0]
                avisos.append(f"«{variable['name']}»: se ha vuelto a unir a «{union.nombre}» por nombre, tipo y papel")
            else:
                union.motivo = ("Hay varias señales coincidentes; vuelva a unir arrastrando" if len(candidatas) > 1
                                else "señal no encontrada")
        if senal is not None:
            if senal["type"].lower() != union.tipo.lower():
                union.motivo = "El tipo de la señal ha cambiado"
            elif senal["kind"].lower() != union.papel:
                union.motivo = "El papel de la señal ha cambiado"
            else:
                union.nombre = senal["name"]
        if union.motivo:
            nombre = variable["name"] if variable else union.nombre
            avisos.append(f"«{nombre}»: {union.motivo}")
    return avisos
