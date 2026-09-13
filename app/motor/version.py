"""La versión de shape101  ·  un solo lugar (mismo patrón que draw101).

  · el número se declara una vez, aquí;
  · app/electron/package.json lo repite porque electron-builder exige semver,
    y el flujo de armado se niega si no coinciden;
  · la app lo enseña en /api/salud y en la barra de estado.
"""
from __future__ import annotations

VERSION = "0.1.0"
FECHA = "2026-09-13"

# Qué trae cada entrega, en el idioma del taller. La más nueva arriba.
BITACORA: list[dict] = [
    {
        "version": "0.1.0",
        "fecha": "2026-09-13",
        "cambios": [
            "Primera versión que se puede instalar y usar, para probar el camino: una pieza con "
            "nombre, material y espesor; tablero; barrenos y cortes rectangulares pasantes; "
            "redondear las esquinas verticales; jalar cualquier cara en 3D (clic y arrastre, o "
            "una medida tecleada); historial editable; guardar y abrir .s101; exportar STEP, STL y glTF.",
            "Lo que NO trae todavía: bocetos dibujados en draw101 (sólo formas paramétricas), "
            "bocetos en otros planos, cortes ciegos, revolucionar, chaflanes, vistas 2D a draw101, "
            "actualizador. Cada cosa tiene su bloque en el plan del chat de shape101.",
            "Medidas en mm con centésimas. Un documento = una pieza.",
        ],
    },
]
