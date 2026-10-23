import { ApiError } from '../contracts.js'
import { type Column, type DataQuery, optionsSchema } from './contracts.js'
import { convert } from './csv.js'

export function expression(column: Column, key: string) {
  const value = `(r.values->>${key})`
  return column.type === 'integer' || column.type === 'decimal' ? `${value}::numeric` : column.type === 'boolean' ? `${value}::boolean` : value
}
export function buildQuery(versionId: string, columns: Column[], query: DataQuery) {
  const parameters: unknown[] = [versionId]
  const parameter = (value: unknown) => { parameters.push(value); return '$'+parameters.length }
  const clauses = ['r.version_id=$1']
  const find = (id: string) => {
    const column = columns.find(column => column.id === id)
    if (!column) throw new ApiError(422,'unknown_column','Colonne inconnue dans cette version.')
    return column
  }
  const normalized = (value: string, column: Column) => {
    try { return convert(value,{...column,dateFormat:'iso',booleanFormat:'true-false'},optionsSchema.parse({missingMarkers:[]})) }
    catch { throw new ApiError(422,'invalid_filter','Valeur de filtre incompatible. Utilisez les formats canoniques : décimales avec point, dates ISO et true/false.') }
  }
  if (query.search) clauses.push(`EXISTS (SELECT 1 FROM jsonb_each_text(r.values) cell WHERE position(lower(${parameter(query.search)}) in lower(cell.value))>0)`)
  for (const filter of query.filters) {
    const column = find(filter.column), value = expression(column,parameter(column.id))
    const {op,values} = filter
    if (op === 'missing' || op === 'present') {
      if(values.length) throw new ApiError(422,'invalid_filter','Ce filtre ne prend pas de valeur.')
      clauses.push(`${value} IS ${op==='present'?'NOT ':''}NULL`); continue
    }
    const textOperation = ['contains','starts_with'].includes(op)
    if ((textOperation && column.type !== 'text') || (['gt','lt'].includes(op) && !['integer','decimal'].includes(column.type)) ||
      (['gte','lte'].includes(op) && !['integer','decimal','date','datetime'].includes(column.type)) ||
      (['before','after'].includes(op) && !['date','datetime'].includes(column.type)) || (op==='between' && !['integer','decimal','date','datetime'].includes(column.type)))
      throw new ApiError(422,'invalid_filter','Opération incompatible avec le type de colonne.')
    if (values.length !== (op==='between'?2:op==='in'?values.length:1) || !values.length) throw new ApiError(422,'invalid_filter','Nombre de valeurs de filtre invalide.')
    if (op==='contains' || op==='starts_with') {
      const input = parameter(values[0]!)
      clauses.push(op==='contains' ? `position(lower(${input}) in lower(${value}))>0` : `left(lower(${value}),length(${input}))=lower(${input})`)
    } else if(op==='in') {
      clauses.push('('+values.map(item=>`${value}=${parameter(normalized(item,column))}`).join(' OR ')+')')
    } else if (op==='between') {
      const lower=normalized(values[0]!,column), upper=normalized(values[1]!,column)
      // SQL performs the actual comparison; ordering rules match the column type.
      clauses.push(`${value} BETWEEN ${parameter(lower)} AND ${parameter(upper)}`)
    } else {
      const operator = {equals:'=',gt:'>',gte:'>=',lt:'<',lte:'<=',before:'<',after:'>'}[op]
      clauses.push(`${value}${operator}${parameter(normalized(values[0]!,column))}`)
    }
  }
  const countParameters=[...parameters]
  const order = query.sort ? `${expression(find(query.sort.column),parameter(query.sort.column))} ${query.sort.direction==='asc'?'ASC':'DESC'} NULLS LAST, r.row_number ASC` : 'r.row_number ASC'
  return { where:clauses.join(' AND '), order, parameters, countParameters }
}
