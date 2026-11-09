"""Lee la forma de onda de cada live_loop de Sonic Pi 5 directamente de la memoria compartida de SuperSonic (/dev/shm/SuperSonic_<puerto>).
Solo lectura y sin dependencias. Si el segmento no existe o no tiene el formato esperado, todo devuelve None y el editor sigue sin onda."""
import mmap, os, struct

MAGIC = 0x5C09E008
CAMPOS = ["magic", "blob_offset", "blob_size", "in_ring_offset", "in_ring_size", "out_ring_offset", "out_ring_size", "nrt_out_ring_offset", "nrt_out_ring_size",
          "control_offset", "metrics_offset", "metrics_field_count", "node_tree_offset", "node_tree_header_bytes", "node_tree_entry_bytes", "node_tree_max_nodes",
          "audio_offset", "audio_slot_count", "audio_slot_bytes", "scope_offset", "scope_max", "scope_header_bytes", "scope_slot_bytes", "scope_slot_header",
          "scope_ring_frames", "scope_channels"]
NIVELES = "▁▂▃▄▅▆▇█"
COLUMNAS = 16            # celdas de la onda junto a cada bucle

class Osciloscopio:
    def __init__(self, ruta):
        self.ruta, self.m, self.h = ruta, None, None

    @classmethod
    def del_motor(cls, puerto):
        return cls(f"/dev/shm/SuperSonic_{puerto}")

    def abrir(self):
        """True si el segmento esta abierto y su cabecera es valida."""
        if self.m is not None: return True
        try:
            fd = os.open(self.ruta, os.O_RDONLY)
            try: m = mmap.mmap(fd, 0, prot=mmap.PROT_READ)
            finally: os.close(fd)
            n = len(CAMPOS)
            if len(m) < 4 * n: m.close(); return False
            h = dict(zip(CAMPOS, struct.unpack_from("<" + "I" * n, m, 0)))
            fin = h["blob_offset"] + h["scope_offset"] + h["scope_header_bytes"] + h["scope_max"] * h["scope_slot_bytes"]
            if h["magic"] != MAGIC or not h["scope_max"] or h["scope_slot_header"] < 32 or fin > len(m): m.close(); return False
        except (OSError, ValueError, struct.error):
            return False
        self.m, self.h = m, h
        return True

    def cerrar(self):
        if self.m is not None:
            try: self.m.close()
            except (BufferError, ValueError): pass
        self.m = self.h = None

    def muestras(self, slot):
        """Canal izquierdo del anillo del slot, de la muestra mas antigua a la mas reciente; None si el slot no esta en uso."""
        if not self.abrir() or not 0 <= slot < self.h["scope_max"]: return None
        h = self.h
        o = h["blob_offset"] + h["scope_offset"] + h["scope_header_bytes"] + slot * h["scope_slot_bytes"]
        try:
            estado, canales, cap, _ = struct.unpack_from("<IIII", self.m, o)
            wp, = struct.unpack_from("<Q", self.m, o + 16)
            if not estado or not canales or not cap or o + h["scope_slot_header"] + cap * canales * 4 > len(self.m): return None
            datos = struct.unpack_from(f"<{cap * canales}f", self.m, o + h["scope_slot_header"])
        except (struct.error, ValueError):
            return None
        izq = datos[::canales]
        i = wp % cap
        return izq[i:] + izq[:i]

def envolvente(muestras, columnas=COLUMNAS):
    """Pico absoluto de cada tramo (0..1) para dibujar la forma de la onda en `columnas` celdas."""
    n = len(muestras)
    if not n: return [0.0] * columnas
    return [min(1.0, max(map(abs, muestras[i * n // columnas:(i + 1) * n // columnas] or (0.0,)))) for i in range(columnas)]

def niveles_texto(env):
    """Envolvente -> indices 0..8 (0 = silencio, 1..8 = alturas de ▁..█); la raiz hace visibles los sonidos suaves."""
    return [0 if v < 0.004 else 1 + min(7, int(v ** 0.6 * 8)) for v in env]
