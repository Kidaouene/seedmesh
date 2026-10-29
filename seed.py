"""SeedMesh hmac-legacy : seed reproductible par namespace."""
import hmac, hashlib, os
MASTER_SEED = int(os.environ.get("SEEDMESH_MASTER_SEED", 987654))
def seed_for(namespace: str, master: int = MASTER_SEED) -> int:
    d = hmac.new(b"SeedMesh", f"{master}:{namespace}".encode(), hashlib.sha256).digest()
    return int.from_bytes(d[:4], "big")
STRICT = {"temperature": 0, "top_p": 1, "threads": os.cpu_count() or 4}
if __name__ == "__main__":
    attendu = {"ia-locale": 692423819, "image-01": 3080848434, "texte-01": 807412180}
    for ns, v in attendu.items():
        assert seed_for(ns) == v, ns
    print("Vecteurs OK")
