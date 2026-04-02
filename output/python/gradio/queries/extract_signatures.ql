/**
 * @name Extract Python function signatures with type annotations
 * @description For fuzz driver generation: function name, file, parameter names and type hints
 * @kind table
 * @id py/tool-function-signatures
 */

import python

string formatTuple(Tuple t) {
  if not exists(t.getElt(1)) then result = formatTypeHint(t.getElt(0))
  else if not exists(t.getElt(2)) then result = formatTypeHint(t.getElt(0)) + ", " + formatTypeHint(t.getElt(1))
  else if not exists(t.getElt(3)) then result = formatTypeHint(t.getElt(0)) + ", " + formatTypeHint(t.getElt(1)) + ", " + formatTypeHint(t.getElt(2))
  else result = formatTypeHint(t.getElt(0)) + ", " + formatTypeHint(t.getElt(1)) + ", ..."
}

string formatTypeHint(Expr annotation) {
  if annotation instanceof Name then result = annotation.(Name).getId()
  else if annotation instanceof Attribute then result = formatTypeHint(annotation.(Attribute).getObject()) + "." + annotation.(Attribute).getName()
  else if annotation instanceof BinaryExpr then result = formatTypeHint(annotation.(BinaryExpr).getLeft()) + " | " + formatTypeHint(annotation.(BinaryExpr).getRight())
  else if annotation instanceof Subscript then result = formatTypeHint(annotation.(Subscript).getObject()) + "[" + formatTypeHint(annotation.(Subscript).getIndex()) + "]"
  else if annotation instanceof Tuple then result = formatTuple(annotation)
  else if annotation instanceof Str then result = annotation.(Str).getS()
  else result = annotation.toString()
}

from Function f, Parameter p
where
  p = f.getAnArg() or p = f.getAKeywordOnlyArg() or p = f.getVararg() or p = f.getKwarg()
select
  f.getName() as name,
  f.getLocation().getFile().getRelativePath() as file,
  f.getLocation().getStartLine() as start_line,
  f.getLocation().getEndLine() as end_line,
  p.getName() as param_name,
  formatTypeHint(p.getAnnotation()) as param_type