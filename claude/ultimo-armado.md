# Último armado

- corrido: 2026-09-25T18:41:18Z
- rama: claude/publicar-0.21.8
- commit: 855bbece2bca3aa818aca3be88022f71751518ff

## Cómo salió cada paso

```json
{
  "version": {
    "outputs": {
      "version": "0.21.8"
    },
    "outcome": "success",
    "conclusion": "success"
  },
  "carga": {
    "outputs": {
      "sha256": "5ac0d826b0fd89144692820ac371532ad17f35e605452d320510d601c8e7e3fe",
      "bytes": "340965685"
    },
    "outcome": "success",
    "conclusion": "success"
  },
  "cargar": {
    "outputs": {
      "cargado": "si"
    },
    "outcome": "success",
    "conclusion": "success"
  }
}
```

## Lo que imprimieron (últimas 400 líneas)

```
sin parches pendientes
core/version.py dice 0.21.8
Python empotrado heredado de: https://github.com/mikebalcazar/descargas/releases/download/shape101-0.21.6/shape101-0.21.6-setup.exe
python empotrado ok
Collecting build123d
  Downloading build123d-0.13.0-py3-none-any.whl.metadata (14 kB)
Collecting cadquery-ocp-novtk<8.1,>=8.0 (from build123d)
  Downloading cadquery_ocp_novtk-8.0.1.0.0-cp311-cp311-win_amd64.whl.metadata (910 bytes)
Collecting typing_extensions<5,>=4.16.0 (from build123d)
  Downloading typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting numpy<3,>=2 (from build123d)
  Downloading numpy-2.4.6-cp311-cp311-win_amd64.whl.metadata (6.6 kB)
Collecting svgpathtools<2,>=1.5.1 (from build123d)
  Downloading svgpathtools-1.8.0-py2.py3-none-any.whl.metadata (22 kB)
Collecting anytree<3,>=2.8.0 (from build123d)
  Downloading anytree-2.13.0-py3-none-any.whl.metadata (8.0 kB)
Collecting ezdxf<2,>=1.1.0 (from build123d)
  Downloading ezdxf-1.4.4-cp311-cp311-win_amd64.whl.metadata (10 kB)
Collecting fonttools<5,>=4.39.0 (from build123d)
  Downloading fonttools-4.66.0-cp311-cp311-win_amd64.whl.metadata (131 kB)
Collecting ipython<10,>=8.0.0 (from build123d)
  Downloading ipython-9.17.1-py3-none-any.whl.metadata (4.6 kB)
Collecting ocpsvg<0.8,>=0.7 (from build123d)
  Downloading ocpsvg-0.7.0-py3-none-any.whl.metadata (918 bytes)
Collecting ocp_gordon<0.4,>=0.3.1 (from build123d)
  Downloading ocp_gordon-0.3.1-py3-none-any.whl.metadata (5.2 kB)
Collecting trianglesolver (from build123d)
  Downloading trianglesolver-1.2-py3-none-any.whl.metadata (1.7 kB)
Collecting sympy (from build123d)
  Downloading sympy-1.14.0-py3-none-any.whl.metadata (12 kB)
Collecting scipy (from build123d)
  Downloading scipy-1.17.1-cp311-cp311-win_amd64.whl.metadata (60 kB)
Collecting scikit-learn<2,>=1.5 (from build123d)
  Downloading scikit_learn-1.9.1-cp311-cp311-win_amd64.whl.metadata (9.3 kB)
Collecting webcolors~=24.8.0 (from build123d)
  Downloading webcolors-24.8.0-py3-none-any.whl.metadata (2.6 kB)
Collecting requests<3,>=2.32 (from build123d)
  Downloading requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
Collecting lib3mf>=2.4.1 (from build123d)
  Downloading lib3mf-2.5.0-py3-none-win_amd64.whl.metadata (6.2 kB)
Collecting bd_materials<0.3.0,>=0.2.0 (from build123d)
  Downloading bd_materials-0.2.4-py3-none-any.whl.metadata (32 kB)
Collecting threejs-materials<1.3.0,>=1.2.1 (from build123d)
  Downloading threejs_materials-1.2.3-py3-none-any.whl.metadata (56 kB)
Collecting cadquery-ocp-proxy==8.0.1.0.0 (from cadquery-ocp-novtk<8.1,>=8.0->build123d)
  Downloading cadquery_ocp_proxy-8.0.1.0.0-py3-none-any.whl.metadata (4.7 kB)
Collecting pyparsing>=3.0.0 (from ezdxf<2,>=1.1.0->build123d)
  Downloading pyparsing-3.3.3-py3-none-any.whl.metadata (5.9 kB)
Collecting colorama>=0.4.4 (from ipython<10,>=8.0.0->build123d)
  Downloading colorama-0.4.6-py2.py3-none-any.whl.metadata (17 kB)
Collecting ipython-pygments-lexers>=1.0.0 (from ipython<10,>=8.0.0->build123d)
  Downloading ipython_pygments_lexers-1.1.1-py3-none-any.whl.metadata (1.1 kB)
Collecting jedi>=0.18.2 (from ipython<10,>=8.0.0->build123d)
  Downloading jedi-0.20.0-py2.py3-none-any.whl.metadata (23 kB)
Collecting matplotlib-inline>=0.1.6 (from ipython<10,>=8.0.0->build123d)
  Downloading matplotlib_inline-0.2.2-py3-none-any.whl.metadata (2.4 kB)
Collecting prompt_toolkit<3.1.0,>=3.0.41 (from ipython<10,>=8.0.0->build123d)
  Downloading prompt_toolkit-3.0.53-py3-none-any.whl.metadata (6.4 kB)
Collecting psutil>=7 (from ipython<10,>=8.0.0->build123d)
  Downloading psutil-7.2.2-cp37-abi3-win_amd64.whl.metadata (22 kB)
Collecting pygments>=2.14.0 (from ipython<10,>=8.0.0->build123d)
  Downloading pygments-2.21.0-py3-none-any.whl.metadata (2.5 kB)
Collecting stack_data>=0.6.0 (from ipython<10,>=8.0.0->build123d)
  Downloading stack_data-0.6.3-py3-none-any.whl.metadata (18 kB)
Collecting traitlets>=5.13.0 (from ipython<10,>=8.0.0->build123d)
  Downloading traitlets-5.16.1-py3-none-any.whl.metadata (10 kB)
Collecting svgelements<2,>=1.9.1 (from ocpsvg<0.8,>=0.7->build123d)
  Downloading svgelements-1.9.6-py2.py3-none-any.whl.metadata (44 kB)
Collecting wcwidth>=0.1.4 (from prompt_toolkit<3.1.0,>=3.0.41->ipython<10,>=8.0.0->build123d)
  Downloading wcwidth-0.9.1-cp310-abi3-win_amd64.whl.metadata (24 kB)
Collecting charset_normalizer<4,>=2 (from requests<3,>=2.32->build123d)
  Downloading charset_normalizer-3.5.1-cp311-cp311-win_amd64.whl.metadata (46 kB)
Collecting idna<4,>=2.5 (from requests<3,>=2.32->build123d)
  Downloading idna-3.20-py3-none-any.whl.metadata (7.2 kB)
Collecting urllib3<3,>=1.26 (from requests<3,>=2.32->build123d)
  Downloading urllib3-2.8.0-py3-none-any.whl.metadata (7.4 kB)
Collecting certifi>=2023.5.7 (from requests<3,>=2.32->build123d)
  Downloading certifi-2026.7.22-py3-none-any.whl.metadata (2.5 kB)
Collecting joblib>=1.4.0 (from scikit-learn<2,>=1.5->build123d)
  Downloading joblib-1.6.0-py3-none-any.whl.metadata (6.5 kB)
Collecting narwhals>=2.0.1 (from scikit-learn<2,>=1.5->build123d)
  Downloading narwhals-2.26.0-py3-none-any.whl.metadata (15 kB)
Collecting threadpoolctl>=3.5.0 (from scikit-learn<2,>=1.5->build123d)
  Downloading threadpoolctl-3.7.0-py3-none-any.whl.metadata (24 kB)
Collecting svgwrite (from svgpathtools<2,>=1.5.1->build123d)
  Downloading svgwrite-1.4.3-py3-none-any.whl.metadata (8.8 kB)
Collecting pillow<12.3.0,>=12.2.0 (from threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading pillow-12.2.0-cp311-cp311-win_amd64.whl.metadata (9.0 kB)
Collecting pygltflib<2.0,>=1.16 (from threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading pygltflib-1.16.5-py3-none-any.whl.metadata (33 kB)
Collecting platformdirs<5.0.0,>=4.9.6 (from threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading platformdirs-4.11.14-py3-none-any.whl.metadata (5.5 kB)
Collecting dataclasses-json>=0.0.25 (from pygltflib<2.0,>=1.16->threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading dataclasses_json-0.6.7-py3-none-any.whl.metadata (25 kB)
Collecting deprecated (from pygltflib<2.0,>=1.16->threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading deprecated-1.3.1-py2.py3-none-any.whl.metadata (5.9 kB)
Collecting marshmallow<4.0.0,>=3.18.0 (from dataclasses-json>=0.0.25->pygltflib<2.0,>=1.16->threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading marshmallow-3.26.2-py3-none-any.whl.metadata (7.3 kB)
Collecting typing-inspect<1,>=0.4.0 (from dataclasses-json>=0.0.25->pygltflib<2.0,>=1.16->threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading typing_inspect-0.9.0-py3-none-any.whl.metadata (1.5 kB)
Collecting packaging>=17.0 (from marshmallow<4.0.0,>=3.18.0->dataclasses-json>=0.0.25->pygltflib<2.0,>=1.16->threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading packaging-26.3-py3-none-any.whl.metadata (3.5 kB)
Collecting mypy-extensions>=0.3.0 (from typing-inspect<1,>=0.4.0->dataclasses-json>=0.0.25->pygltflib<2.0,>=1.16->threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
Collecting parso<0.9.0,>=0.8.6 (from jedi>=0.18.2->ipython<10,>=8.0.0->build123d)
  Downloading parso-0.8.7-py2.py3-none-any.whl.metadata (8.2 kB)
Collecting cloudpickle>=3.0 (from joblib>=1.4.0->scikit-learn<2,>=1.5->build123d)
  Downloading cloudpickle-3.1.2-py3-none-any.whl.metadata (7.1 kB)
Collecting executing>=1.2.0 (from stack_data>=0.6.0->ipython<10,>=8.0.0->build123d)
  Downloading executing-2.2.1-py2.py3-none-any.whl.metadata (8.9 kB)
Collecting asttokens>=2.1.0 (from stack_data>=0.6.0->ipython<10,>=8.0.0->build123d)
  Downloading asttokens-3.0.2-py3-none-any.whl.metadata (5.7 kB)
Collecting pure-eval (from stack_data>=0.6.0->ipython<10,>=8.0.0->build123d)
  Downloading pure_eval-0.2.4-py3-none-any.whl.metadata (6.4 kB)
Collecting wrapt<3,>=1.10 (from deprecated->pygltflib<2.0,>=1.16->threejs-materials<1.3.0,>=1.2.1->build123d)
  Downloading wrapt-2.4.1-cp311-cp311-win_amd64.whl.metadata (7.6 kB)
Collecting mpmath<1.4,>=1.1.0 (from sympy->build123d)
  Downloading mpmath-1.3.0-py3-none-any.whl.metadata (8.6 kB)
Downloading build123d-0.13.0-py3-none-any.whl (387 kB)
Downloading anytree-2.13.0-py3-none-any.whl (45 kB)
Downloading bd_materials-0.2.4-py3-none-any.whl (74 kB)
Downloading cadquery_ocp_novtk-8.0.1.0.0-cp311-cp311-win_amd64.whl (47.5 MB)
   ---------------------------------------- 47.5/47.5 MB 36.4 MB/s  0:00:01
Downloading cadquery_ocp_proxy-8.0.1.0.0-py3-none-any.whl (3.2 kB)
Downloading ezdxf-1.4.4-cp311-cp311-win_amd64.whl (3.0 MB)
   ---------------------------------------- 3.0/3.0 MB 57.4 MB/s  0:00:00
Downloading fonttools-4.66.0-cp311-cp311-win_amd64.whl (1.6 MB)
   ---------------------------------------- 1.6/1.6 MB 42.9 MB/s  0:00:00
Downloading ipython-9.17.1-py3-none-any.whl (639 kB)
   ---------------------------------------- 639.0/639.0 kB 12.2 MB/s  0:00:00
Downloading numpy-2.4.6-cp311-cp311-win_amd64.whl (12.6 MB)
   ---------------------------------------- 12.6/12.6 MB 131.3 MB/s  0:00:00
Downloading ocp_gordon-0.3.1-py3-none-any.whl (52 kB)
Downloading ocpsvg-0.7.0-py3-none-any.whl (20 kB)
Downloading prompt_toolkit-3.0.53-py3-none-any.whl (392 kB)
Downloading requests-2.34.2-py3-none-any.whl (73 kB)
Downloading charset_normalizer-3.5.1-cp311-cp311-win_amd64.whl (206 kB)
Downloading idna-3.20-py3-none-any.whl (69 kB)
Downloading scikit_learn-1.9.1-cp311-cp311-win_amd64.whl (8.3 MB)
   ---------------------------------------- 8.3/8.3 MB 130.1 MB/s  0:00:00
Downloading svgelements-1.9.6-py2.py3-none-any.whl (137 kB)
Downloading svgpathtools-1.8.0-py2.py3-none-any.whl (70 kB)
Downloading threejs_materials-1.2.3-py3-none-any.whl (89.8 MB)
   ---------------------------------------- 89.8/89.8 MB 36.5 MB/s  0:00:02
Downloading pillow-12.2.0-cp311-cp311-win_amd64.whl (7.1 MB)
   ---------------------------------------- 7.1/7.1 MB 86.3 MB/s  0:00:00
Downloading platformdirs-4.11.14-py3-none-any.whl (26 kB)
Downloading pygltflib-1.16.5-py3-none-any.whl (27 kB)
Downloading typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Downloading urllib3-2.8.0-py3-none-any.whl (135 kB)
Downloading webcolors-24.8.0-py3-none-any.whl (15 kB)
Downloading certifi-2026.7.22-py3-none-any.whl (136 kB)
Downloading colorama-0.4.6-py2.py3-none-any.whl (25 kB)
Downloading dataclasses_json-0.6.7-py3-none-any.whl (28 kB)
Downloading marshmallow-3.26.2-py3-none-any.whl (50 kB)
Downloading typing_inspect-0.9.0-py3-none-any.whl (8.8 kB)
Downloading ipython_pygments_lexers-1.1.1-py3-none-any.whl (8.1 kB)
Downloading jedi-0.20.0-py2.py3-none-any.whl (4.9 MB)
   ---------------------------------------- 4.9/4.9 MB 59.3 MB/s  0:00:00
Downloading parso-0.8.7-py2.py3-none-any.whl (107 kB)
Downloading joblib-1.6.0-py3-none-any.whl (306 kB)
Downloading cloudpickle-3.1.2-py3-none-any.whl (22 kB)
Downloading lib3mf-2.5.0-py3-none-win_amd64.whl (857 kB)
   ---------------------------------------- 857.6/857.6 kB 18.6 MB/s  0:00:00
Downloading matplotlib_inline-0.2.2-py3-none-any.whl (9.5 kB)
Downloading mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
Downloading narwhals-2.26.0-py3-none-any.whl (474 kB)
Downloading packaging-26.3-py3-none-any.whl (129 kB)
Downloading psutil-7.2.2-cp37-abi3-win_amd64.whl (137 kB)
Downloading pygments-2.21.0-py3-none-any.whl (1.3 MB)
   ---------------------------------------- 1.3/1.3 MB 31.9 MB/s  0:00:00
Downloading pyparsing-3.3.3-py3-none-any.whl (126 kB)
Downloading scipy-1.17.1-cp311-cp311-win_amd64.whl (36.6 MB)
   ---------------------------------------- 36.6/36.6 MB 72.7 MB/s  0:00:00
Downloading stack_data-0.6.3-py3-none-any.whl (24 kB)
Downloading asttokens-3.0.2-py3-none-any.whl (28 kB)
Downloading executing-2.2.1-py2.py3-none-any.whl (28 kB)
Downloading threadpoolctl-3.7.0-py3-none-any.whl (26 kB)
Downloading traitlets-5.16.1-py3-none-any.whl (86 kB)
Downloading wcwidth-0.9.1-cp310-abi3-win_amd64.whl (596 kB)
   ---------------------------------------- 596.7/596.7 kB 20.9 MB/s  0:00:00
Downloading deprecated-1.3.1-py2.py3-none-any.whl (11 kB)
Downloading wrapt-2.4.1-cp311-cp311-win_amd64.whl (98 kB)
Downloading pure_eval-0.2.4-py3-none-any.whl (11 kB)
Downloading svgwrite-1.4.3-py3-none-any.whl (67 kB)
Downloading sympy-1.14.0-py3-none-any.whl (6.3 MB)
   ---------------------------------------- 6.3/6.3 MB 128.5 MB/s  0:00:00
Downloading mpmath-1.3.0-py3-none-any.whl (536 kB)
   ---------------------------------------- 536.2/536.2 kB 17.1 MB/s  0:00:00
Downloading trianglesolver-1.2-py3-none-any.whl (5.4 kB)
Installing collected packages: trianglesolver, svgelements, pure-eval, mpmath, lib3mf, wrapt, webcolors, wcwidth, urllib3, typing_extensions, traitlets, threadpoolctl, sympy, svgwrite, pyparsing, pygments, psutil, platformdirs, pillow, parso, packaging, numpy, narwhals, mypy-extensions, idna, fonttools, executing, colorama, cloudpickle, charset_normalizer, certifi, cadquery-ocp-proxy, asttokens, anytree, typing-inspect, stack_data, scipy, requests, prompt_toolkit, ocpsvg, matplotlib-inline, marshmallow, joblib, jedi, ipython-pygments-lexers, ezdxf, deprecated, cadquery-ocp-novtk, svgpathtools, scikit-learn, ocp_gordon, ipython, dataclasses-json, pygltflib, threejs-materials, bd_materials, build123d

Successfully installed anytree-2.13.0 asttokens-3.0.2 bd_materials-0.2.4 build123d-0.13.0 cadquery-ocp-novtk-8.0.1.0.0 cadquery-ocp-proxy-8.0.1.0.0 certifi-2026.7.22 charset_normalizer-3.5.1 cloudpickle-3.1.2 colorama-0.4.6 dataclasses-json-0.6.7 deprecated-1.3.1 executing-2.2.1 ezdxf-1.4.4 fonttools-4.66.0 idna-3.20 ipython-9.17.1 ipython-pygments-lexers-1.1.1 jedi-0.20.0 joblib-1.6.0 lib3mf-2.5.0 marshmallow-3.26.2 matplotlib-inline-0.2.2 mpmath-1.3.0 mypy-extensions-1.1.0 narwhals-2.26.0 numpy-2.4.6 ocp_gordon-0.3.1 ocpsvg-0.7.0 packaging-26.3 parso-0.8.7 pillow-12.2.0 platformdirs-4.11.14 prompt_toolkit-3.0.53 psutil-7.2.2 pure-eval-0.2.4 pygltflib-1.16.5 pygments-2.21.0 pyparsing-3.3.3 requests-2.34.2 scikit-learn-1.9.1 scipy-1.17.1 stack_data-0.6.3 svgelements-1.9.6 svgpathtools-1.8.0 svgwrite-1.4.3 sympy-1.14.0 threadpoolctl-3.7.0 threejs-materials-1.2.3 traitlets-5.16.1 trianglesolver-1.2 typing-inspect-0.9.0 typing_extensions-4.16.0 urllib3-2.8.0 wcwidth-0.9.1 webcolors-24.8.0 wrapt-2.4.1
kernel y app conviven; caja de prueba con 6 caras
773M	runtime/python
Downloading Chrome for Testing 153.0.8010.12 (playwright chromium v1243)[2m from https://cdn.playwright.dev/builds/cft/153.0.8010.12/win64/chrome-win64.zip[22m
|                                                                                |   0% of 195.6 MiB
|■■■■■■■■                                                                        |  10% of 195.6 MiB
|■■■■■■■■■■■■■■■■                                                                |  20% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■                                                        |  30% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                                |  40% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                        |  50% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                |  60% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                        |  70% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                |  80% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■        |  90% of 195.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100% of 195.6 MiB
Chrome for Testing 153.0.8010.12 (playwright chromium v1243) downloaded to C:\Users\runneradmin\AppData\Local\ms-playwright\chromium-1243
Downloading FFmpeg (playwright ffmpeg v1011)[2m from https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-win64.zip[22m
|                                                                                |   0% of 1.3 MiB
|■■■■■■■■                                                                        |  10% of 1.3 MiB
|■■■■■■■■■■■■■■■■                                                                |  20% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■                                                        |  30% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                                |  40% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                        |  50% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                |  60% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                        |  70% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                |  80% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■        |  90% of 1.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100% of 1.3 MiB
FFmpeg (playwright ffmpeg v1011) downloaded to C:\Users\runneradmin\AppData\Local\ms-playwright\ffmpeg-1011
Downloading Chrome Headless Shell 153.0.8010.12 (playwright chromium-headless-shell v1243)[2m from https://cdn.playwright.dev/builds/cft/153.0.8010.12/win64/chrome-headless-shell-win64.zip[22m
|                                                                                |   0% of 114.6 MiB
|■■■■■■■■                                                                        |  10% of 114.6 MiB
|■■■■■■■■■■■■■■■■                                                                |  20% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■                                                        |  30% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                                |  40% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                        |  50% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                |  60% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                        |  70% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                |  80% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■        |  90% of 114.6 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100% of 114.6 MiB
Chrome Headless Shell 153.0.8010.12 (playwright chromium-headless-shell v1243) downloaded to C:\Users\runneradmin\AppData\Local\ms-playwright\chromium_headless_shell-1243
Downloading Winldd (playwright winldd v1007)[2m from https://cdn.playwright.dev/dbazure/download/playwright/builds/winldd/1007/winldd-win64.zip[22m
|■■■■■■■■                                                                        |  12% of 0.1 MiB
|■■■■■■■■■■■■■■■■                                                                |  25% of 0.1 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■                                                        |  38% of 0.1 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                        |  50% of 0.1 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                |  63% of 0.1 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                        |  75% of 0.1 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                |  88% of 0.1 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100% of 0.1 MiB
Winldd (playwright winldd v1007) downloaded to C:\Users\runneradmin\AppData\Local\ms-playwright\winldd-1007

  shape101 0.21.8 (2026-09-25)  ·  42 pruebas

  ok   t001_dxf         DXF: ida y vuelta, y lo ajeno intacto         36 comprobaciones      263 ms
  ok   t002_historial   deshacer, rehacer, transacciones, orden y tope  15 comprobaciones       10 ms
  ok   t003_capas       plantilla, nombres, grosores, herencia y bloqueo  34 comprobaciones        1 ms
  ok   t004_proyecto    .101s, guardado atómico, autoguardado y recuperación  26 comprobaciones     1576 ms
  ok   t005_interfaz    el programa manejado con un navegador real    30 comprobaciones    17340 ms
  ok   t006_entrada     las ocho referencias, ortho y las cuatro formas de dar un punto  36 comprobaciones     6706 ms
  ok   t007_dibujo      dibujar y editar con el ratón, con geometría exacta  17 comprobaciones     9017 ms
  ok   t008_cotas       medida, asociatividad, capa y DIMENSION       20 comprobaciones       48 ms
  ok   t009_papel       escala real, recorte, pie de plano y PDF      26 comprobaciones      202 ms
  ok   t010_suite       t101x: bloques, cotas, regenerar sin perder anotaciones, paquete  27 comprobaciones     1230 ms
  ok   t011_flujo       el día completo: cocina → hoja → PDF → DXF → guardar y reabrir  18 comprobaciones      133 ms
[3d] kernel listo en 2.9 s
  ok   t012_dwg         DWG R2013 con los dos motores, capas y unidades  14 comprobaciones    11166 ms
  ok   t013_ajeno       un plano de fuera: se pica y se borra, pero no se le hace osnap  10 comprobaciones     7140 ms
  ok   t014_rapidez     el parche no crece con el plano, y lo pintado es lo que hay   8 comprobaciones     1239 ms
  ok   t015_unir        UNIR: cadenas, arcos en los dos sentidos, y lo que no toca  29 comprobaciones        1 ms
  ok   t016_negativos   medidas negativas en rectángulo (cajita y comandos) y en línea  17 comprobaciones    13174 ms
  ok   t017_tecleado_vs_snap el valor tecleado manda sobre el snap (línea y rectángulo)  11 comprobaciones    14520 ms
  ok   t018_escalard    ESCALARD escala sólo sobre el eje base→referencia  13 comprobaciones    13792 ms
  ok   t019_recortar_polilinea RECORTAR quita un trozo de polilínea y deja polilíneas  19 comprobaciones    17675 ms
  ok   t020_cuerpo_extruir extruir un contorno y volverlo sólido         18 comprobaciones      119 ms
  ok   t021_cuerpo_jalar_cara jalar una cara y que la pieza se rehaga       12 comprobaciones      252 ms
  ok   t022_cuerpo_mover_punto mover un punto y que la pieza se reconstruya  11 comprobaciones      171 ms
  ok   t023_oda         ODA: sólo opendesign.com por https, y sha256 del puntero antes de msiexec  28 comprobaciones        5 ms
  ok   t024_planos      extruir sobre XZ y YZ: la pieza sale a donde debe  11 comprobaciones       42 ms
  ok   t025_tiradores   tiradores: vértices y aristas del sólido, cada uno independiente  56 comprobaciones     5602 ms
  ok   t026_historial_pieza historial de la pieza: pasos en palabras, números que se tocan  44 comprobaciones     6474 ms
  ok   t027_boceto_cotas boceto con cotas: teclear el ancho en vez de arrastrar puntos  51 comprobaciones     5373 ms
  ok   t028_nombrado_partido nombrado cuando una cara se parte en dos (el riesgo de la etapa C)  36 comprobaciones      506 ms
  ok   t029_ids_operaciones cada operación con su id: archivos viejos, dos bocetos, nombres que no se mueven  29 comprobaciones      213 ms
  ok   t030_model       model: revolver, barrer, loft y extruir-cara, con sus nombres  33 comprobaciones      219 ms
  ok   t031_model_desde_el_dibujo model desde el dibujo: REVOLVER, BARRER, LOFT y CRECER  37 comprobaciones     5350 ms
  ok   t032_rejilla_y_encuadre la rejilla: por ventana, por plano e infinita; y el cero al centro  38 comprobaciones    14795 ms
  ok   t033_importar_de_draw importar un dibujo 2D de draw101 y levantarlo  24 comprobaciones     9528 ms
  ok   t034_dibujo_en_perspectiva dibujar en la ventana donde está el ratón, sobre su plano  10 comprobaciones     7928 ms
  ok   t035_hule_por_el_plano el trazo en curso se pinta acostado en su plano, también en perspectiva  10 comprobaciones     8223 ms
  ok   t036_supr_extruir_rotar Supr borra la pieza señalada · EXTRUIR + valor + Enter · ROTAR entre planos  18 comprobaciones    14327 ms
  ok   t037_camara_anclada la Perspectiva orbita alrededor de su mira, panea sin deformar, y Extents la ancla en lo seleccionado  13 comprobaciones     9462 ms
  ok   t038_seleccion_entre_planos seleccionar de canto desde la Lateral, encajonar en pantalla, y rotar lo seleccionado a la pared  11 comprobaciones    11085 ms
  ok   t039_osnap_entre_planos osnap desde la Frontal y la Lateral: pega a lo de canto y no inventa referencias   9 comprobaciones    11111 ms
  ok   t040_solidos_directos PRISMA, CILINDRO, CONO, ESFERA y PIRAMIDE: sólidos directos sobre el plano de la ventana  25 comprobaciones    10376 ms
  ok   t041_rotar_con_referencia ROTAR: centro, punto de referencia y punto nuevo (o los grados a los que debe quedar)   9 comprobaciones    15468 ms
  ok   t042_estilos_de_vista ESTILO básico · alámbrico fantasma · renderizado, con el color de la capa de material  14 comprobaciones     8387 ms

  Todo bien: 953 comprobaciones en 42 pruebas ·  260250 ms
shape101-0.21.8-setup.exe: 340965685 bytes · sha256 5ac0d826b0fd89144692820ac371532ad17f35e605452d320510d601c8e7e3fe · 9 pedazos · tag shape101-0.21.8
remote: 
remote: Create a pull request for 'claude/carga-shape101-0.21.8' on GitHub by visiting:        
remote:      https://github.com/mikebalcazar/descargas/pull/new/claude/carga-shape101-0.21.8        
remote: 
rama claude/carga-shape101-0.21.8 empujada; publicar-instalador.yml arranca solo en descargas
release aún no existe (404), reintento 1
release aún no existe (404), reintento 2
release shape101-0.21.8 publicada y comprobada: 340965685 bytes · sha256 cuadra ✓
```
