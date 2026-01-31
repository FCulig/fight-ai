import numpy as np

def cosine_sim(a, b):
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return -1.0
    return float(np.dot(a, b) / (na * nb))

class IdentityMemory:
    """Keeps at most MAX_FIGHTER_IDS identities with EMA mean embedding."""
    def __init__(self, max_ids=2, ema=0.9, sim_threshold=0.75):
        """
        Initialize an IdentityMemory instance for tracking fighter identities.
        
        Args:
            max_ids (int): Maximum number of distinct fighter identities to maintain. Defaults to 2.
            ema (float): Exponential Moving Average factor for updating embeddings. Controls how much
                         new embeddings influence the mean. Defaults to EMA constant.
            sim_threshold (float): Minimum cosine similarity score required to match a new embedding
                                   to an existing identity. Defaults to SIM_THRESHOLD constant.
        """
        self.max_ids = max_ids
        self.ema = ema
        self.sim_threshold = sim_threshold
        self.mem = {}
        self.next_id = 0

    def assign(self, emb):
        """Return (reid_id, sim). Creates new ID only if under max_ids."""
        if hasattr(emb, "detach"):
            emb = emb.detach().cpu().numpy()
        emb = emb.astype(np.float32)

        if not self.mem:
            self.mem[0] = emb
            self.next_id = 1
            return 0, 1.0

        best_id, best_sim = None, -1.0
        for rid, mean_emb in self.mem.items():
            s = cosine_sim(emb, mean_emb)
            if s > best_sim:
                best_sim, best_id = s, rid

        if best_sim >= self.sim_threshold:
            self.mem[best_id] = self.ema * self.mem[best_id] + (1.0 - self.ema) * emb
            return int(best_id), float(best_sim)

        # New identity only if we still have room (cap at 2 fighters)
        if len(self.mem) < self.max_ids:
            rid = self.next_id
            self.mem[rid] = emb
            self.next_id += 1
            return int(rid), float(best_sim)

        # Already have 2 IDs: force-assign to closest to avoid ID explosion
        self.mem[best_id] = self.ema * self.mem[best_id] + (1.0 - self.ema) * emb
        return int(best_id), float(best_sim)