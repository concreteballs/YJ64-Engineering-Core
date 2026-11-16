"""Declarative plugin capability manifests; never loads or executes plugin code."""
from __future__ import annotations
import hashlib, json, re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

_API="1.0"
_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_VERSION=re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

def _strings(values: Iterable[str], name: str) -> tuple[str,...]:
    result=tuple(values)
    if any(not isinstance(x,str) or not x.strip() for x in result) or len(set(result))!=len(result):
        raise ValueError(f"{name} must contain unique non-empty strings")
    return result

def _canonical(value: Any) -> str:
    try: return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(",",":"))
    except (TypeError,ValueError) as exc: raise ValueError(f"metadata must be finite JSON: {exc}") from exc

@dataclass(frozen=True)
class ExtensionDependency:
    extension_id: str
    version: str
    def __post_init__(self):
        if not _ID.fullmatch(self.extension_id) or not _VERSION.fullmatch(self.version): raise ValueError("invalid extension dependency")

@dataclass(frozen=True)
class ExtensionCapability:
    operation: str
    input_schema: str
    output_schema: str
    units: tuple[str,...]=()
    coordinate_frames: tuple[str,...]=()
    time_scales: tuple[str,...]=()
    def __post_init__(self):
        for key in ("operation","input_schema","output_schema"):
            if not isinstance(getattr(self,key),str) or not getattr(self,key).strip(): raise ValueError(f"{key} must be non-empty")
        for key in ("units","coordinate_frames","time_scales"): object.__setattr__(self,key,_strings(getattr(self,key),key))

@dataclass(frozen=True)
class ExtensionManifest:
    extension_id: str
    name: str
    version: str
    kind: str
    capabilities: tuple[ExtensionCapability,...]
    api_version: str=_API
    dependencies: tuple[ExtensionDependency,...]=()
    licence: str="UNSPECIFIED"
    permissions: tuple[str,...]=()
    safety_class: str="general"
    network_required: bool=False
    offline_supported: bool=False
    resource_requirements: Mapping[str,Any]=field(default_factory=dict)
    provenance: Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if not _ID.fullmatch(self.extension_id): raise ValueError("invalid extension_id")
        for key in ("name","kind","api_version","licence","safety_class"):
            if not isinstance(getattr(self,key),str) or not getattr(self,key).strip(): raise ValueError(f"{key} must be non-empty")
        if not _VERSION.fullmatch(self.version): raise ValueError("version must use semantic version syntax")
        if not self.capabilities: raise ValueError("at least one capability is required")
        if len({c.operation for c in self.capabilities})!=len(self.capabilities): raise ValueError("capability operations must be unique")
        if len({d.extension_id for d in self.dependencies})!=len(self.dependencies): raise ValueError("dependencies must be unique")
        object.__setattr__(self,"permissions",_strings(self.permissions,"permissions"))
        if not isinstance(self.network_required,bool) or not isinstance(self.offline_supported,bool): raise TypeError("network/offline flags must be booleans")
        if self.network_required and self.offline_supported: raise ValueError("network-required extension cannot claim offline support")
        _canonical(dict(self.resource_requirements)); _canonical(dict(self.provenance))
    def to_dict(self): return asdict(self)
    def to_json(self): return _canonical(self.to_dict())
    def fingerprint(self): return hashlib.sha256(self.to_json().encode()).hexdigest()
    @classmethod
    def from_dict(cls,data: Mapping[str,Any]):
        if not isinstance(data,Mapping): raise TypeError("manifest must be an object")
        p=dict(data)
        p["capabilities"]=tuple(x if isinstance(x,ExtensionCapability) else ExtensionCapability(**x) for x in p.get("capabilities",()))
        p["dependencies"]=tuple(x if isinstance(x,ExtensionDependency) else ExtensionDependency(**x) for x in p.get("dependencies",()))
        if "permissions" in p: p["permissions"]=tuple(p["permissions"])
        return cls(**p)
    @classmethod
    def from_json(cls,source: str):
        try: data=json.loads(source,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid JSON constant {x}")))
        except (TypeError,json.JSONDecodeError) as exc: raise ValueError(f"invalid manifest JSON: {exc}") from exc
        return cls.from_dict(data)

@dataclass(frozen=True)
class CapabilityRequirement:
    operation: str
    units: tuple[str,...]=()
    coordinate_frame: str|None=None
    time_scale: str|None=None
    input_schema: str|None=None
    output_schema: str|None=None

class ExtensionRegistry:
    """Registry of declared capabilities, separate from executable plugin loading."""
    def __init__(self,supported_api_versions: Iterable[str]=(_API,)):
        self._api=frozenset(_strings(supported_api_versions,"supported_api_versions"))
        self._items: dict[str,ExtensionManifest]={}
    @property
    def manifests(self): return dict(self._items)
    def register(self,manifest: ExtensionManifest):
        if not isinstance(manifest,ExtensionManifest): raise TypeError("manifest must be ExtensionManifest")
        if manifest.api_version not in self._api: raise ValueError(f"unsupported extension API: {manifest.api_version}")
        if manifest.extension_id in self._items: raise ValueError(f"extension already registered: {manifest.extension_id}")
        self._items[manifest.extension_id]=manifest
    def validate_dependencies(self) -> dict[str,tuple[str,...]]:
        problems={}
        for eid,item in self._items.items():
            missing=tuple(d.extension_id for d in item.dependencies if (d.extension_id not in self._items or self._items[d.extension_id].version!=d.version))
            if missing: problems[eid]=missing
        return problems
    def get(self,extension_id: str) -> ExtensionManifest:
        try: return self._items[extension_id]
        except KeyError as exc: raise KeyError(f"unknown extension: {extension_id}") from exc
    def find_compatible(self,requirement: CapabilityRequirement) -> tuple[ExtensionManifest,...]:
        if not isinstance(requirement,CapabilityRequirement): raise TypeError("requirement must be CapabilityRequirement")
        broken=self.validate_dependencies()
        found=[]
        for item in self._items.values():
            if item.extension_id in broken: continue
            for cap in item.capabilities:
                if cap.operation!=requirement.operation: continue
                if requirement.input_schema and cap.input_schema!=requirement.input_schema: continue
                if requirement.output_schema and cap.output_schema!=requirement.output_schema: continue
                if requirement.units and not set(requirement.units).issubset(cap.units): continue
                if requirement.coordinate_frame and requirement.coordinate_frame not in cap.coordinate_frames: continue
                if requirement.time_scale and requirement.time_scale not in cap.time_scales: continue
                found.append(item); break
        return tuple(sorted(found,key=lambda x:x.extension_id))
