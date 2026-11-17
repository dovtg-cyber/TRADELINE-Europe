"""Client workspaces. Law is shared; client documents are private. Every read is checked and audited."""
from __future__ import annotations
import time
from dataclasses import dataclass


class AccessDenied(Exception):
    pass


@dataclass
class ClientDoc:
    doc_id: str
    owner: str
    name: str
    text: str


class WorkspaceStore:
    def __init__(self) -> None:
        self._docs: dict[str, ClientDoc] = {}
        self._grants: set[tuple[str, str]] = set()   # (reviewer_id, doc_id): explicit, per document
        self.audit: list[dict] = []

    def _log(self, actor: str, action: str, doc_id: str, allowed: bool) -> None:
        self.audit.append({"ts": time.time(), "actor": actor, "action": action, "doc_id": doc_id, "allowed": allowed})

    def put(self, owner: str, doc: ClientDoc) -> None:
        if doc.owner != owner:
            self._log(owner, "put", doc.doc_id, False)
            raise AccessDenied("a user can only store documents under their own account")
        self._docs[doc.doc_id] = doc
        self._log(owner, "put", doc.doc_id, True)

    def grant(self, owner: str, reviewer: str, doc_id: str) -> None:
        d = self._docs.get(doc_id)
        if d is None or d.owner != owner:
            raise AccessDenied("only the owner can grant access")
        self._grants.add((reviewer, doc_id))
        self._log(owner, f"grant:{reviewer}", doc_id, True)

    def get(self, actor: str, doc_id: str) -> ClientDoc:
        d = self._docs.get(doc_id)
        ok = d is not None and (d.owner == actor or (actor, doc_id) in self._grants)
        self._log(actor, "get", doc_id, ok)
        if not ok:
            raise AccessDenied("no access")            # same answer for 'missing' and 'not yours': no existence leak
        return d

    def context_for(self, actor: str) -> list[ClientDoc]:
        """What may enter the model context for this user: their own documents only."""
        out = [d for d in self._docs.values() if d.owner == actor]
        self._log(actor, "context", "*", True)
        return out
