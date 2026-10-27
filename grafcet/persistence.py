"""Persistencia abierta del proyecto (documento 09; REQ-DAT-01..08, REQ-ROB-02, REQ-EDT-10, REQ-PLT-02).

- Proyecto = carpeta con manifest.json y documentos «familia-hexID.json» (P-IMP-03).
- Guardado atómico en resultado observable: los documentos nuevos se escriben como
  «.new», se confirma un diario commit.json y después se promueven con os.replace. Al
  abrir, un diario presente se completa; los «.new» sin diario se descartan. Nunca queda
  un proyecto válido mezclado de dos revisiones (T-22d).
- Política de versiones: mayor desconocida → ni ejecutar ni sobrescribir; menor desconocida
  → solo lectura si el documento declara minorAddsSemantics=false (P-IMP-07).
- Sin rutas absolutas, ascensos ni recursos de red (D-RUTA); límites antes de leer (D-LIM-DATOS).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .canonical import CanonicalError, canonical_bytes, digest, sha256_hex, strict_loads
from .diagnostics import Diagnostic, DiagnosticError
from .ids import document_filename, document_id_fits, valid_id
from .model import unknown_fields
from .profile import APP_VERSION, FORMAT_VERSION, NORMATIVE_BASE, PROFILE_ID, PROFILE_VERSION

MAX_FILE = 100 * 1024 * 1024
MAX_PROJECT = 500 * 1024 * 1024
SUPPORTED_MAJOR, SUPPORTED_MINOR = 0, 1
FAMILIES = {"project", "model", "presentation", "scenario", "snapshot", "test-catalog"}
MANIFEST = "manifest.json"
JOURNAL = "commit.json"
RECOVERY_DIR = ".recuperacion"
AUTOSAVE_PERIOD_S = 30
PROJECT_FIELDS = {"family", "formatVersion", "id", "title", "normativeBase", "modelRefs", "scenarioRefs",
                  "presentationRefs", "capabilityProfile"}


# --- Sistema de ficheros (puerto) ----------------------------------------------------

class FileSystem:
    """Adaptador local. `fail_after_writes` simula una interrupción para pruebas (T-22d)."""

    def __init__(self, fail_after_writes: int | None = None) -> None:
        self.fail_after_writes = fail_after_writes
        self.writes = 0

    def _tick(self) -> None:
        if self.fail_after_writes is not None and self.writes >= self.fail_after_writes:
            raise OSError("interrupción simulada del guardado")
        self.writes += 1

    def write_durable(self, path: Path, data: bytes) -> None:
        self._tick()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    def replace(self, src: Path, dst: Path) -> None:
        self._tick()
        os.replace(src, dst)

    def read(self, path: Path, limit: int = MAX_FILE) -> bytes:
        size = path.stat().st_size
        if size > limit:
            raise DiagnosticError(Diagnostic("D-LIM-DATOS", f"{path.name}: {size} bytes superan el límite {limit}"))
        return path.read_bytes()

    def remove(self, path: Path) -> None:
        path.unlink(missing_ok=True)


# --- Documentos ----------------------------------------------------------------------

@dataclass
class Loaded:
    doc: dict[str, Any] | None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    executable: bool = True
    writable: bool = True


def new_document(family: str, ident: str, **fields: Any) -> dict[str, Any]:
    return {"family": family, "formatVersion": FORMAT_VERSION, "id": ident, **fields}


def parse_document(data: bytes, family: str | None = None) -> Loaded:
    try:
        doc = strict_loads(data)
    except CanonicalError as exc:
        code = "D-LIM-DATOS" if "profundidad" in str(exc) else "D-FORMATO"
        return Loaded(None, [Diagnostic(code, f"documento ilegible: {exc}")], False, False)
    if not isinstance(doc, dict) or doc.get("family") not in FAMILIES:
        return Loaded(None, [Diagnostic("D-FORMATO", "familia de documento desconocida o ausente")], False, False)
    if family is not None and doc["family"] != family:
        return Loaded(None, [Diagnostic("D-FORMATO", f"se esperaba familia {family}, no {doc['family']}")], False, False)
    if not valid_id(doc.get("id")):
        return Loaded(None, [Diagnostic("D-ID", f"ID de documento inválido: {doc.get('id')!r}")], False, False)
    ver = doc.get("formatVersion")
    parts = ver.split(".") if isinstance(ver, str) else []
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return Loaded(None, [Diagnostic("D-FORMATO", f"formatVersion inválida: {ver!r}")], False, False)
    major, minor = int(parts[0]), int(parts[1])
    if major != SUPPORTED_MAJOR:
        return Loaded(doc, [Diagnostic("D-FORMATO", f"versión mayor {major} desconocida: no se ejecuta ni se sobrescribe",
                                       element=doc["id"])], executable=False, writable=False)
    if minor > SUPPORTED_MINOR:
        if doc.get("minorAddsSemantics") is not False:
            return Loaded(doc, [Diagnostic("D-FORMATO", f"versión menor {minor} desconocida sin declarar "
                                           "minorAddsSemantics=false: rechazo explícito", element=doc["id"])],
                          executable=False, writable=False)
        return Loaded(doc, [Diagnostic("D-FORMATO", f"versión menor {minor}: lectura completa preservando campos",
                                       element=doc["id"], severity="advertencia")], executable=True, writable=False)
    diags = []
    for name, ext in (doc.get("extensions") or {}).items():
        if not (isinstance(ext, dict) and ext.get("affectsSemantics") is False):
            diags.append(Diagnostic("D-FORMATO", f"extensión semántica no reconocida «{name}»: bloquea la simulación; "
                                    "se conserva", element=doc["id"], severity="bloqueo"))
    return Loaded(doc, diags, executable=not diags, writable=True)


def safe_path(root: Path, rel: Any) -> Path:
    """Resuelve una referencia relativa dentro de la raíz o lanza D-RUTA (REQ-DAT-06)."""
    bad = (not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or "\\" in rel or ":" in rel
           or any(part in ("", ".", "..") for part in rel.split("/")) or "://" in rel)
    if not bad:
        target = (root / rel).resolve()
        bad = not target.is_relative_to(root.resolve())
    if bad:
        raise DiagnosticError(Diagnostic("D-RUTA", f"referencia fuera de la raíz o no relativa: {rel!r}"))
    return root / rel


# --- Proyecto ------------------------------------------------------------------------

@dataclass
class Project:
    manifest: dict[str, Any]
    documents: dict[str, dict[str, Any]]  # ruta relativa -> documento
    diagnostics: list[Diagnostic] = field(default_factory=list)
    writable: bool = True
    executable: bool = True

    def doc(self, family: str, ident: str) -> dict[str, Any]:
        return self.documents[document_filename(family, ident)]

    def models(self) -> list[dict[str, Any]]:
        return [self.documents[r["path"]] for r in self.manifest["modelRefs"]]


def new_project(ident: str, title: str) -> Project:
    manifest = new_document("project", ident, title=title, normativeBase=dict(NORMATIVE_BASE), modelRefs=[],
                            scenarioRefs=[], presentationRefs=[],
                            capabilityProfile={"id": PROFILE_ID, "version": PROFILE_VERSION},
                            appVersion=APP_VERSION)
    return Project(manifest, {})


def add_document(project: Project, doc: dict[str, Any]) -> str:
    fam, ident = doc["family"], doc["id"]
    if not document_id_fits(fam, ident):
        raise DiagnosticError(Diagnostic("D-ID", f"el ID de documento {ident!r} produce un nombre de fichero de más de "
                                         "255 bytes (H-12)", element=ident))
    path = document_filename(fam, ident)
    key = {"model": "modelRefs", "scenario": "scenarioRefs", "presentation": "presentationRefs"}.get(fam)
    if key is not None and not any(r["id"] == ident for r in project.manifest[key]):
        project.manifest[key].append({"id": ident, "path": path})
    project.documents[path] = doc
    return path


def _encode(doc: dict[str, Any]) -> bytes:
    return canonical_bytes(doc) + b"\n"


def save_project(root: Path, project: Project, fs: FileSystem | None = None) -> str:
    """Guarda el proyecto completo; devuelve el digest del manifiesto guardado. Si falla, la
    versión anterior queda íntegra y recuperable."""
    fs = fs or FileSystem()
    if not project.writable:
        raise DiagnosticError(Diagnostic("D-FORMATO", "documento con versión o semántica desconocida: no se sobrescribe"))
    root.mkdir(parents=True, exist_ok=True)
    _recover_journal(root, fs)
    payloads = {path: _encode(doc) for path, doc in sorted(project.documents.items())}
    manifest = dict(project.manifest)
    manifest["documentDigests"] = {p: sha256_hex(b) for p, b in payloads.items()}
    payloads[MANIFEST] = _encode(manifest)
    for path, data in payloads.items():
        safe_path(root, path)
        fs.write_durable(root / (path + ".new"), data)
    fs.write_durable(root / (JOURNAL + ".tmp"), _encode({"promote": sorted(payloads)}))
    fs.replace(root / (JOURNAL + ".tmp"), root / JOURNAL)  # punto de confirmación
    _recover_journal(root, fs)
    for fam in FAMILIES:
        for f in root.glob(f"{fam}-*.json"):
            if f.name not in payloads:
                fs.remove(f)  # documentos que ya no figuran en el manifiesto
    project.manifest = manifest
    return sha256_hex(payloads[MANIFEST])


def _recover_journal(root: Path, fs: FileSystem) -> None:
    journal = root / JOURNAL
    if journal.exists():
        entries = strict_loads(journal.read_bytes())["promote"]
        for path in entries:
            src = root / (path + ".new")
            if src.exists():
                fs.replace(src, root / path)
        journal.unlink()
    for leftover in list(root.glob("*.new")) + list(root.glob(JOURNAL + ".tmp")):
        leftover.unlink()  # escritura interrumpida antes de confirmar: se descarta


def open_project(root: Path, fs: FileSystem | None = None) -> Project:
    fs = fs or FileSystem()
    _recover_journal(root, fs)
    total = sum(f.stat().st_size for f in root.glob("*.json"))
    if total > MAX_PROJECT:
        raise DiagnosticError(Diagnostic("D-LIM-DATOS", f"proyecto de {total} bytes supera {MAX_PROJECT}"))
    loaded = parse_document(fs.read(root / MANIFEST), "project")
    if loaded.doc is None:
        raise DiagnosticError(*loaded.diagnostics)
    manifest = loaded.doc
    diags = list(loaded.diagnostics)
    missing = PROJECT_FIELDS - set(manifest)
    if missing:
        raise DiagnosticError(Diagnostic("D-FORMATO", f"manifiesto sin campos obligatorios: {sorted(missing)}"))
    nb = manifest["normativeBase"]
    if not isinstance(nb, dict) or nb.get("standard") != "IEC 60848" or nb.get("edition") != "3.0":
        diags.append(Diagnostic("D-FORMATO", "normativeBase debe declarar IEC 60848:2013 edición 3.0; no se sustituye "
                                "silenciosamente", field="normativeBase"))
    project = Project(manifest, {}, diags, loaded.writable, loaded.executable)
    digests = manifest.get("documentDigests", {})
    seen_ids: dict[str, str] = {}
    for key, family in (("modelRefs", "model"), ("scenarioRefs", "scenario"), ("presentationRefs", "presentation")):
        refs = manifest[key]
        ids = [r.get("id") for r in refs if isinstance(r, dict)]
        if len(ids) != len(set(ids)):
            project.diagnostics.append(Diagnostic("D-FORMATO", f"{key} contiene repetidos"))
        for ref in refs:
            path = safe_path(root, ref.get("path") if isinstance(ref, dict) else None)
            rel = ref["path"]
            if rel != document_filename(family, ref["id"]):
                raise DiagnosticError(Diagnostic("D-REF", f"la ruta {rel} no corresponde al ID {ref['id']}"))
            data = fs.read(path)
            if rel in digests and digests[rel] != sha256_hex(data):
                raise DiagnosticError(Diagnostic("D-INTEGRIDAD", f"digest de {rel} no coincide con el manifiesto"))
            doc = parse_document(data, family)
            project.diagnostics.extend(doc.diagnostics)
            if doc.doc is None:
                raise DiagnosticError(*doc.diagnostics)
            if doc.doc["id"] != ref["id"]:
                raise DiagnosticError(Diagnostic("D-REF", f"{rel} contiene el ID {doc.doc['id']}, no {ref['id']}"))
            if family == "model":
                unknown = unknown_fields(doc.doc)
                if unknown:
                    project.diagnostics.append(Diagnostic(
                        "D-FORMATO", f"campos semánticos desconocidos {unknown}: no ejecutable ni sobrescribible; se "
                        "conservan", element=doc.doc["id"], severity="bloqueo"))
                    doc.writable = doc.executable = False
            project.writable &= doc.writable
            project.executable &= doc.executable
            project.documents[rel] = doc.doc
            for ident in _element_ids(doc.doc):
                if ident in seen_ids and seen_ids[ident] != rel:
                    project.diagnostics.append(Diagnostic("D-ID", f"ID {ident} repetido entre {seen_ids[ident]} y {rel}",
                                                          element=ident))
                seen_ids.setdefault(ident, rel)
    return project


@dataclass
class OpenedModel:
    doc: dict[str, Any]
    presentations: list[dict[str, Any]]  # las que dibujan este modelo (modelId)
    title: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    executable: bool = True


def open_model(path: Path, fs: FileSystem | None = None) -> OpenedModel:
    """Abre un modelo para simularlo (P-IMP-29): la carpeta de un proyecto o su manifest.json (primer modelo del
    proyecto, con sus presentaciones) o un documento de modelo suelto (con las presentaciones de su misma
    carpeta). Aplica las mismas reglas de versión, integridad, límites y campos desconocidos que open_project."""
    fs = fs or FileSystem()
    path = Path(path)
    if path.is_dir() or path.name == MANIFEST:
        root = path if path.is_dir() else path.parent
        project = open_project(root, fs)
        models = project.models()
        if not models:
            raise DiagnosticError(Diagnostic("D-REF", "el proyecto no contiene ningún modelo"))
        doc = models[0]
        pres = [d for d in (project.documents[r["path"]] for r in project.manifest["presentationRefs"])
                if d.get("modelId") == doc["id"]]
        return OpenedModel(doc, pres, project.manifest.get("title") or doc["id"], project.diagnostics,
                           project.executable)
    loaded = parse_document(fs.read(path))
    if loaded.doc is None:
        raise DiagnosticError(*loaded.diagnostics)
    if loaded.doc["family"] == "project":
        return open_model(path.parent, fs)
    if loaded.doc["family"] != "model":
        raise DiagnosticError(Diagnostic("D-FORMATO", f"se esperaba un modelo o un proyecto, no un documento "
                                         f"«{loaded.doc['family']}»", element=loaded.doc["id"]))
    doc, diags, executable = loaded.doc, list(loaded.diagnostics), loaded.executable
    unknown = unknown_fields(doc)
    if unknown:
        diags.append(Diagnostic("D-FORMATO", f"campos semánticos desconocidos {unknown}: no ejecutable", element=doc["id"],
                                severity="bloqueo"))
        executable = False
    pres = []
    for f in sorted(path.parent.glob("presentation-*.json")):
        p = parse_document(fs.read(f), "presentation")
        if p.doc is not None and p.doc.get("modelId") == doc["id"]:
            pres.append(p.doc)
    return OpenedModel(doc, pres, path.stem, diags, executable)


def _element_ids(doc: dict[str, Any]) -> list[str]:
    out = [doc["id"]]
    if doc["family"] == "model":
        for coll in ("partials", "steps", "transitions", "variables", "expressions", "actions", "forces", "draftLinks"):
            out += [x.get("id") for x in doc.get(coll, []) if isinstance(x, dict)]
        for coll in ("macros", "expansions", "enclosures"):
            out += [x.get("id") for x in (doc.get("hierarchy") or {}).get(coll, []) if isinstance(x, dict)]
    return [i for i in out if isinstance(i, str)]


def validate_presentation(pres: dict[str, Any], model: dict[str, Any]) -> list[Diagnostic]:
    ids = set(_element_ids(model))
    diags = []
    for lay in pres.get("elementLayouts", []):
        if lay.get("elementRef") not in ids:
            diags.append(Diagnostic("D-REF", f"layout apunta a un elemento inexistente: {lay.get('elementRef')}"))
    for note in pres.get("notes", []):
        if "elementRef" in note and note["elementRef"] not in ids:
            diags.append(Diagnostic("D-REF", f"nota asociada a un elemento inexistente: {note['elementRef']}"))
    return diags


# --- Recuperación separada (REQ-EDT-10) ----------------------------------------------

class Recovery:
    def __init__(self, root: Path, fs: FileSystem | None = None) -> None:
        self.dir = root / RECOVERY_DIR
        self.fs = fs or FileSystem()
        self.last_save_s: float | None = None

    def maybe_autosave(self, now_s: float, dirty: bool, project: Project, revision: str) -> bool:
        if not dirty or (self.last_save_s is not None and now_s - self.last_save_s < AUTOSAVE_PERIOD_S):
            return False
        recovery = Project(dict(project.manifest), dict(project.documents))
        recovery.manifest["recovery"] = {"revision": revision, "savedAtS": str(int(now_s))}
        save_project(self.dir, recovery, self.fs)
        self.last_save_s = now_s
        return True

    def available(self) -> dict[str, Any] | None:
        if not (self.dir / MANIFEST).exists():
            return None
        return open_project(self.dir, self.fs).manifest.get("recovery")

    def load(self) -> Project:
        return open_project(self.dir, self.fs)


# --- Migración explícita (REQ-DAT-03, T-22e) -----------------------------------------

def migrate_project(src: Path, dst: Path, steps: list[Callable[[dict[str, Any]], tuple[dict[str, Any], list[str]]]]
                    ) -> dict[str, Any]:
    """Crea una copia migrada y un informe; el original no se toca. Nunca cambia la edición
    normativa ni el perfil (no hay migración automática entre ediciones o perfiles)."""
    if dst.resolve() == src.resolve():
        raise DiagnosticError(Diagnostic("D-RUTA", "la migración debe escribir en una carpeta distinta"))
    project = open_project(src)
    report: dict[str, Any] = {"source": str(src.name), "changes": [], "affectedRequirements": ["REQ-DAT-03"]}
    before_norm, before_prof = dict(project.manifest["normativeBase"]), dict(project.manifest["capabilityProfile"])
    for path, doc in list(project.documents.items()):
        for step in steps:
            doc, changes = step(doc)
            report["changes"] += [f"{path}: {c}" for c in changes]
        project.documents[path] = doc
    if project.manifest["normativeBase"] != before_norm or project.manifest["capabilityProfile"] != before_prof:
        raise DiagnosticError(Diagnostic("D-FORMATO", "una migración no puede cambiar edición normativa ni perfil"))
    save_project(dst, project)
    (dst / "informe-migracion.json").write_bytes(canonical_bytes(report) + b"\n")
    report["digest"] = digest(report["changes"])
    return report
