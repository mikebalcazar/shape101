# Los motores de DWG, y con qué licencia vienen

t101draw lee y escribe DWG con dos motores de terceros que viajan dentro del
programa. Esto es lo que son y bajo qué condiciones se pueden usar. Conviene
tenerlo por escrito antes de que haga falta, no después.

## LibreDWG — GNU, **GPL-3.0**

- Paquete: `@mlightcad/libredwg-web` (LibreDWG 0.13.4 compilado a WebAssembly)
- Autor del empaquetado: MLight Lee · Motor: GNU LibreDWG
- Origen: <https://www.gnu.org/software/libredwg/>

Es el lector de DWG con más kilómetros: lee de R13 a R2018. La GPL-3 dice, en
corto: **puedes usarlo para lo que quieras; si distribuyes un programa que lo
incluye, tienes que entregar también el código fuente de ese programa, bajo
GPL-3.**

Qué significa para Taller 101, dicho claro:

- **Uso interno del taller: no hay ninguna obligación.** Usar un programa no es
  distribuirlo. Instalarlo en las máquinas del taller tampoco.
- **El día que t101draw se le entregue a alguien de fuera** —un cliente, otro
  taller, y con más razón si se cobra— hay dos caminos honestos: publicar el
  código de t101draw bajo GPL-3, o sacar LibreDWG del paquete. Sin LibreDWG el
  programa **sigue leyendo DWG** con acad-ts, que es MIT; se pierde parte de la
  cobertura en archivos viejos o raros, no la función.

No es una decisión que haya que tomar hoy. Es una que no se puede tomar por
accidente.

## acad-ts — **MIT**

- Paquete: `@node-projects/acad-ts` (puerto en TypeScript de ACadSharp)
- Origen: <https://github.com/node-projects/acad-ts>

La licencia MIT no pide nada más que conservar el aviso de copyright. Está aquí
por tres razones: lee **R2007**, que es justo donde LibreDWG tropieza; **escribe**
DWG, que la compilación de LibreDWG que usamos no hace; y no ata a Taller 101 a
nada.

## Y el ODA File Converter

No viaja dentro del programa: su licencia no permite redistribuirlo. Si está
instalado en la máquina, t101draw lo usa y lo prefiere, porque lo mantiene la
gente que escribió la especificación del DWG y es el más fiel de los tres. Si no
está, no pasa nada — para eso están los otros dos.

Se baja gratis, previo registro, de <https://www.opendesign.com/guestfiles/oda_file_converter>.
