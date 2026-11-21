# Cuándo Llega Jujuy 🚌

Proyecto cívico de información de transporte público para San Salvador de Jujuy.
Nace de la exploración de necesidades locales (nov-2026): tras la reestructuración
de agosto 2026 solo operan **El Urbano** y **Santa Ana**; Xibi Xibi (la única con
app de GPS en tiempo real) perdió la concesión, y el proyecto cívico ColeJUY
pausó su tracking porque la empresa no autorizó mostrar sus datos. Hay un
proyecto de ordenanza (jul-2026) para un Sistema Único de Información en Tiempo
Real del Transporte Urbano, sin implementar.

**Estrategia: no depender de la autorización de las empresas.** Datos abiertos
(OSM) + reportes colaborativos de usuarios.

## Fases

- **Fase 0 (ESTE REPO, funcionando):** recorridos y paradas estáticos desde
  OpenStreetMap (59 relaciones, 926 paradas al 20/11/2026), API + mapa web.
- **Fase 0.5 (HECHA):** asociación espacial paradas↔recorridos (umbral 25 m):
  195 → 6.347 asociaciones; 829/926 paradas con línea; 59/59 sentidos con
  paradas ordenadas por proyección sobre el trazado. Caso testigo: línea 48
  pasó de 6 a 119 paradas (Moovit declara 123 para la 48I: validación externa).
- **Fase 1:** reportes colaborativos por parada ("pasó el 29", "va colmado",
  "no viene hace 40 min") → frecuencia real estimada por franja horaria.
  Backend SQLite + POST /api/reportes, moderación básica anti-spam.
- **Fase 2:** datos oficiales GTFS/GTFS-RT negociados con municipio/empresas
  al calor de la ordenanza; auditoría de cobertura barrio-centro.

## Datos y licencia

- Fuente: colaboradores de OpenStreetMap vía Overpass API.
  Mapeo comunitario: https://wiki.openstreetmap.org/wiki/Jujuy/transporte_publico
- Licencia **ODbL 1.0**: reutilizable con atribución obligatoria
  ("© OpenStreetMap contributors"). La web ya la muestra.
- No se usan datos de Moovit ni de las empresas (propietarios).
- Línea 21 figura con operador Xibi-Xibi (histórico): dato OSM heredado,
  verificar contra la reestructuración 2026 antes de publicar.

## Cómo correrlo (Windows)

```
py -3.13 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe src\descargar_osm.py     # regenera datos/ desde OSM
venv\Scripts\python.exe src\asociar_paradas.py   # asocia paradas a recorridos (25 m)
venv\Scripts\python.exe pruebas\test_datos.py    # valida los datos
venv\Scripts\python.exe pruebas\test_asociacion.py
venv\Scripts\python.exe src\api.py               # http://127.0.0.1:8100
```

## Estructura

```
src/descargar_osm.py   pipeline Overpass → datos/*.json + GeoJSON
src/asociar_paradas.py match espacial parada↔trazado (<=25 m) + orden por proyección
src/api.py             FastAPI: /api/estado /api/lineas /api/lineas/{ref}
                       /api/paradas /api/recorridos.geojson + web estática
web/index.html         mapa Leaflet: elegir línea, ver recorridos ida/vuelta
                       y paradas con las líneas que pasan por cada una
datos/                 generados (lineas, paradas, recorridos, estado, fuente/)
pruebas/test_datos.py  validación de integridad/coordenadas/conteos
```

## Contexto y aliados

- Exploración completa: `../jujuy-exploracion/INFORME_JUJUY_PROYECTOS.md` (P1).
- JujuyDev (jujuy.dev.ar, +600 devs): hackathon a bordo del Tren Solar 22/11/2026;
  el registro era por proyectos → este repo es el proyecto para el próximo evento.
- ColeJUY (Franco Durán): colaborar, no competir — ellos ya tienen comunidad.
- Modelo replicable: Movi (Rosario, 2016).
- Financiamiento posible: programa provincial "AWS Desarrolla" (hasta USD 100k
  en créditos de nube).

## Roadmap inmediato

1. ~~Asociación espacial paradas↔recorridos~~ HECHA (21/11/2026).
2. Validar recorridos OSM contra la realidad post-reestructuración (líneas que
   cambiaron de empresa en ago-2026; ej. línea 29 de Mariano Moreno, ausente
   en OSM; línea 21 figura aún con operador Xibi-Xibi histórico).
3. Fase 1: reportes colaborativos (empezar con 2-3 líneas de alto tráfico).
4. Contacto institucional: concejal Gustavo Martínez (ordenanza jul-2026) y
   municipio (Programa de Transformación Digital).
5. Difusión con la comunidad: JujuyDev, centros vecinales, UNJu.
