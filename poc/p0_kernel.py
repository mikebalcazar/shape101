"""P0 · El kernel con un caso de taller. Corrido el 12-sep-2026 (Linux, Python
3.12, build123d 0.11.1). Imprime los tiempos que están en RESULTADOS.md.

    pip install build123d
    python poc/p0_kernel.py
"""

from __future__ import annotations

import os
import time

from build123d import Axis, BuildPart, BuildSketch, Circle, Cylinder, Locations, Mode, Rectangle, export_step, export_stl, extrude, fillet


def cuenta_aristas(sh) -> int:
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    if sh.IsNull():
        return 0
    ex = TopExp_Explorer(sh, TopAbs_EDGE)
    n = 0
    while ex.More():
        n += 1
        ex.Next()
    return n


def main() -> None:
    t0 = time.perf_counter()
    with BuildPart() as p:
        with BuildSketch():
            Rectangle(900, 600)
            Circle(80, mode=Mode.SUBTRACT)          # barreno ⌀160
        extrude(amount=18)                          # tablero de 18
        with Locations((300, 0, 18)):
            Cylinder(60, 40, mode=Mode.SUBTRACT)    # cajeado (booleana)
        fillet(p.edges().filter_by(Axis.Z), 20)     # redondeos verticales
    t1 = time.perf_counter()
    solido = p.part

    export_step(solido, "prueba.step")
    export_stl(solido, "prueba.stl")
    t2 = time.perf_counter()

    verts, tris = solido.tessellate(0.1)
    t3 = time.perf_counter()

    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    algo = HLRBRep_Algo()
    algo.Add(solido.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))))  # planta
    algo.Update()
    algo.Hide()
    hlr = HLRBRep_HLRToShape(algo)
    visibles, ocultas = cuenta_aristas(hlr.VCompound()), cuenta_aristas(hlr.HCompound())
    t4 = time.perf_counter()

    print(f"modelado (extruir+booleana+redondeo): {1000 * (t1 - t0):.0f} ms")
    print(f"volumen {solido.volume / 1000:.1f} cm3, {len(solido.faces())} caras, {len(solido.edges())} aristas")
    print(f"STEP {os.path.getsize('prueba.step') // 1024} KB + STL {os.path.getsize('prueba.stl') // 1024} KB: {1000 * (t2 - t1):.0f} ms")
    print(f"teselado: {len(verts)} vértices, {len(tris)} triángulos: {1000 * (t3 - t2):.0f} ms")
    print(f"vista 2D con ocultas (HLR, planta): {visibles} visibles, {ocultas} ocultas: {1000 * (t4 - t3):.0f} ms")


if __name__ == "__main__":
    main()
