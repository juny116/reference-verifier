from dataclasses import dataclass, field, asdict

@dataclass
class Reference:
    raw: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    doi: str = ""
    pmid: str = ""
    parser: str = "rules"
    warnings: list[str] = field(default_factory=list)

@dataclass
class Record:
    title: str
    authors: list[str] = field(default_factory=list)
    year: str = ""
    venue: str = ""
    doi: str = ""
    pmid: str = ""
    sources: list[dict] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
