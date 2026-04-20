<!-- Keep the 5 required ## headings exactly as written. CI validates them. -->

## ¿Qué cambia?

<Una descripción breve de qué cambia y por qué.>

## Issue relacionado

Closes #<n>

## Acción según AGENTS.md

- **Ruta (keywords)**: <área / keywords>
- **Docs leídos**:
  - `AGENTS.md`
  - `docs/standards/...`
- **Rol asumido**: <Backend | Security | Docs | ...>

## Auditoría pre-merge

- [ ] 1. Contract and compatibility — `CHANGELOG.md` actualizado si aplica.
- [ ] 2. Security — sin credenciales, sin SQL directo a Netezza, sin `except Exception` sin re-raise.
- [ ] 3. Maintainability — funciones <50 LoC, <4 args, una intención por PR.
- [ ] 4. Tests — nuevos, verdes locales, coverage ≥85%.
- [ ] 5. Typing and style — `ruff` y `mypy --strict` limpios.
- [ ] 6. Documentation — docs actualizados donde aplica.
- [ ] 7. Language and form — título/branch/commits conventional, PR body con los 5 headings.
- [ ] Zero-guess — ninguna asunción silenciosa. Las ambigüedades se preguntan o se exponen como configuración.

## Validación humana

- [ ] Sí — explicar por qué:
- [ ] No — cambio mecánico / cubierto por tests y audit.
