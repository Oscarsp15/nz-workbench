# Netezza SP Workflow

Cuando trabajes con stored procedures de IBM Netezza, sigue este flujo usando las herramientas de nz-workbench.

## ANTES de modificar cualquier SP

**Siempre consulta el contexto primero:**

```
kb_get_sp_context(database="X", schema="Y", name="Z")
```

Esto te muestra:
- Learnings previos (errores resueltos, warnings, reglas de negocio)
- Dependencias de tablas (INSERT, SELECT, UPDATE, DELETE)
- Metadata del SP

**No modifiques código sin revisar el contexto primero.**

## DURANTE el análisis/modificación

### Para buscar patrones o conceptos
```
kb_search(query="cómo se manejan los pagos")
```
Usa búsqueda semántica para preguntas conceptuales.

### Para buscar SPs que tocan una tabla específica
```
kb_search_refs(table="TABLA_X", operation="INSERT")
```
Más preciso que semántica para queries estructurales.

### Para comparar SP entre bases de datos
```
kb_compare_sps(schema="DBO", name="SP_X", database1="PROD_MODELOS", database2="PROD_ANALITICA")
```

### Para ver impacto antes de modificar una tabla
```
kb_get_table_dependencies(table="TABLA_X")
```

## GUARDAR LEARNINGS (después de verificar)

**Guarda SOLO cuando hayas PROBADO y VERIFICADO que tu solución funciona.**

⚠️ NO guardes teorías o hipótesis sin probar. Solo guarda conocimiento verificado.

### Cuando resuelves un error/bug:
```
kb_save_learning(
    database="X", schema="Y", name="Z",
    type="error_solution",
    content="Error: [descripción]. Causa: [causa]. Solución: [solución aplicada]"
)
```

### Cuando descubres lógica de negocio no documentada:
```
kb_save_learning(
    database="X", schema="Y", name="Z",
    type="business_rule",
    content="Este SP [descripción de la regla de negocio]"
)
```

### Cuando encuentras algo peligroso o frágil:
```
kb_save_learning(
    database="X", schema="Y", name="Z",
    type="warning",
    content="CUIDADO: [descripción del riesgo]"
)
```

### Cuando identificas dependencias ocultas:
```
kb_save_learning(
    database="X", schema="Y", name="Z",
    type="dependency_note",
    content="Este SP depende de [dependencia no obvia]"
)
```

## Ejemplo de flujo completo

```
Usuario: "El SP_CALCULO_PAGOS está dando error de división por cero"

1. Consultar contexto:
   → kb_get_sp_context("PROD_MODELOS", "DBO", "SP_CALCULO_PAGOS")

2. [Analizar el código, encontrar que falta validación de monto=0]

3. [Aplicar el fix al código - agregar NULLIF(MONTO, 0)]

4. [PROBAR que el fix funciona - ejecutar el SP, verificar resultado]

5. SOLO después de verificar, guardar el learning:
   → kb_save_learning(
       database="PROD_MODELOS",
       schema="DBO",
       name="SP_CALCULO_PAGOS",
       type="error_solution",
       content="División por cero cuando MONTO=0. Solución verificada: NULLIF(MONTO, 0) en línea 45"
     )
```

## Recordatorio

- **Consulta contexto ANTES de modificar**
- **Prueba y verifica ANTES de guardar learnings**
- **Solo guarda conocimiento verificado, no hipótesis**
- **Usa la herramienta correcta para cada tipo de búsqueda**
