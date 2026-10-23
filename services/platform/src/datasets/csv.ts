import { createHash } from 'node:crypto'
import { Readable } from 'node:stream'
import { setImmediate } from 'node:timers/promises'
import { parse } from 'csv-parse'
import { ApiError } from '../contracts.js'
import { LIMITS, type Column, type Configuration, type Converted, type Issue, type Options, type Parsed, type Validation } from './contracts.js'

export const columnId = (name: string) => 'c_' + createHash('sha256').update(name).digest('hex').slice(0,16)
export function validDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.slice(0,4) < '1000') return false
  const date = new Date(value + 'T00:00:00.000Z')
  return Number.isFinite(date.valueOf()) && date.toISOString().slice(0,10) === value
}
export function dateValue(value: string, format: Column['dateFormat']) {
  if (format === 'iso') return validDate(value) ? value : null
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value)
  if (!match) return null
  const iso = `${match[3]}-${format === 'dmy' ? match[2] : match[1]}-${format === 'dmy' ? match[1] : match[2]}`
  return validDate(iso) ? iso : null
}
export function numeric(value: string, integer = false, comma = false) {
  const normalized = comma ? value.replace(',', '.') : value
  if (!(integer ? /^[+-]?\d+$/ : /^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/).test(normalized)) return null
  const unsigned = normalized.replace(/^[+-]/,'')
  const [whole = '', fraction = ''] = unsigned.split('.')
  if ((whole.replace(/^0+/,'') + fraction).length > 38 || fraction.length > 12) return null
  if (integer) return BigInt(normalized).toString()
  const sign = normalized.startsWith('-') ? '-' : ''
  const left = whole.replace(/^0+(?=\d)/,'') || '0', right = fraction.replace(/0+$/,'')
  const result = left + (right ? '.' + right : '')
  return sign && result !== '0' ? sign + result : result
}
export function convert(value: string, column: Column, configuration: Options): string | boolean | null {
  const candidate = configuration.trim ? value.trim() : value
  if (configuration.missingMarkers.includes(candidate)) return null
  if (column.type === 'text') return candidate
  if (column.type === 'integer' || column.type === 'decimal') {
    const result = numeric(candidate, column.type === 'integer', configuration.decimalSeparator === ',')
    if (result !== null) return result
  } else if (column.type === 'boolean') {
    const tokens = column.booleanFormat === 'oui-non' ? ['oui','non'] : column.booleanFormat === '1-0' ? ['1','0'] : ['true','false']
    const index = tokens.indexOf(candidate.toLowerCase())
    if (index !== -1) return index === 0
  } else if (column.type === 'date') {
    const result = dateValue(candidate,column.dateFormat)
    if (result) return result
  } else if (column.type === 'datetime') {
    const match = /^(\d{4}-\d{2}-\d{2})T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(?:\.(\d{1,6}))?(Z|[+-](?:0\d|1[0-4]):[0-5]\d)$/.exec(candidate)
    if (match && validDate(match[1]!) && !/[+-]14:(?!00)/.test(candidate)) {
      const date = new Date(candidate)
      if (Number.isFinite(date.valueOf()) && date.getUTCFullYear() >= 1000 && date.getUTCFullYear() <= 9999)
        return date.toISOString().slice(0,19)+'.'+(match[5]??'').padEnd(6,'0')+'Z'
    }
  }
  throw new Error('invalid_cell')
}
function detect(text: string): ',' | ';' | '\t' {
  const counts = new Map<','|';'|'\t',number>([[',',0],[';',0],['\t',0]])
  let quoted = false
  for (let index=0; index<Math.min(text.length,65536); index++) {
    const ch = text[index]!
    if (ch === '"') { if (quoted && text[index+1] === '"') index++; else quoted = !quoted }
    else if (!quoted && (ch === '\r' || ch === '\n')) break
    else if (!quoted && counts.has(ch as ',')) counts.set(ch as ',',counts.get(ch as ',')!+1)
  }
  return [...counts].sort((a,b) => b[1]-a[1])[0]![0]
}
export async function parseCsv(content: Buffer, options: Options): Promise<Parsed> {
  if (!content.length || content.length > LIMITS.bytes) throw new ApiError(413,'file_limit','Le fichier doit contenir entre 1 octet et 10 Mio.')
  const result: Parsed = { headers: [], rows: [], issues: [], issueCount: 0, delimiter: ',', warnings: [] }
  const issue = (value: Issue) => { result.issueCount++; if (result.issues.length < LIMITS.issues) result.issues.push(value) }
  let text: string
  try { text = new TextDecoder(options.encoding,{ fatal: true }).decode(content).replace(/^\uFEFF/,'') }
  catch { issue({row:0,line:1,column:null,code:'encoding',message:'Encodage invalide. Choisissez UTF-8 ou Windows-1252, ou réenregistrez le fichier.'}); return result }
  if (text.includes('\0')) { issue({row:0,line:1,column:null,code:'nul_character',message:'Caractère nul ou fichier binaire/UTF-16 non pris en charge.'}); return result }
  result.delimiter = options.delimiter === 'auto' ? detect(text) : options.delimiter
  const parser = parse({ bom:true, delimiter:result.delimiter, relax_column_count:true, skip_empty_lines:false, max_record_size:262144, info:true })
  const bytes = Buffer.from(text,'utf8')
  const source = Readable.from((function* () { for(let start=0; start<bytes.length; start+=65536) yield bytes.subarray(start,start+65536) })())
  source.pipe(parser)
  try {
    let index = 0
    for await (const entry of parser) {
      const cells = entry.record as string[], line = entry.info.lines as number
      if (!index++) {
        result.headers = cells
        if (cells.length > LIMITS.columns) { issue({row:0,line,column:null,code:'column_limit',message:'Maximum : 100 colonnes.'}); break }
        const names = new Set<string>()
        cells.forEach(name => {
          const key = name.trim().toLowerCase()
          if (!key || name.length>160 || /[\u0000-\u001f\u007f]/.test(name)) issue({row:0,line,column:name,code:'invalid_header',message:'En-tête vide, trop long ou avec caractère de contrôle.'})
          if (names.has(key)) issue({row:0,line,column:name,code:'duplicate_header',message:'Les noms de colonnes doivent être uniques, sans distinction de casse ni espaces de bord.'})
          names.add(key)
        })
        continue
      }
      const row = result.rows.length+1
      if (row > LIMITS.rows || row * result.headers.length > LIMITS.cells) { issue({row,line,column:null,code:'row_limit',message:'Maximum : 25 000 lignes et 1 000 000 de cellules.'}); break }
      if (cells.length !== result.headers.length) issue({row,line,column:null,code:'row_width',message:`${cells.length} cellules ; ${result.headers.length} attendues. Aucune ligne ne sera supprimée.`})
      cells.forEach((cell,column) => { if(cell.length > LIMITS.cellCharacters) issue({row,line,column:result.headers[column] ?? null,code:'cell_limit',message:'Une cellule dépasse 16 384 caractères.'}) })
      result.rows.push({cells,line})
      if (row%1000===0) await setImmediate()
    }
  } catch (error) {
    const line = error && typeof error === 'object' && 'lines' in error ? Number(error.lines) || 1 : 1
    issue({row:result.rows.length+1,line,column:null,code:'malformed_csv',message:'CSV mal formé : guillemets, séparateurs ou taille de ligne invalides. Corrigez le fichier source.'})
  } finally { source.destroy(); parser.destroy() }
  if (!result.headers.length || !result.rows.length) issue({row:0,line:1,column:null,code:'empty_csv',message:'Un en-tête et au moins une ligne de données sont requis.'})
  return result
}
export function inferColumns(parsed: Parsed, options: Options): Column[] {
  return parsed.headers.slice(0,LIMITS.columns).map((name,index) => {
    const column: Column = { id:columnId(name),name:name.trim(),originalName:name,type:'text',dateFormat:'iso',booleanFormat:'true-false' }
    const values = parsed.rows.slice(0,200).map(row => row.cells[index] ?? '').map(value => options.trim ? value.trim() : value).filter(value => !options.missingMarkers.includes(value))
    if (!values.length || parsed.rows.some(row=>/^[+-]?0\d+$/.test(options.trim?(row.cells[index]??'').trim():row.cells[index]??''))) return column
    for (const type of ['integer','decimal','boolean','date','datetime'] as const) {
      const trial = { ...column,type }
      if (values.every(value => { try { return convert(value,trial,options) !== undefined } catch { return false } })) { column.type=type; break }
    }
    return column
  })
}
export async function validateRows(parsed: Parsed, config: Configuration): Promise<{ report: Validation; rows: Converted[] }> {
  const issues = [...parsed.issues]; let issueCount = parsed.issueCount
  const rows: Converted[] = []
  if (!parsed.issueCount) for (const [index, row] of parsed.rows.entries()) {
    const values: Converted['values'] = {}, original: Converted['original'] = {}
    config.columns.forEach((column,ordinal) => {
      original[column.id] = row.cells[ordinal]!
      try { values[column.id] = convert(row.cells[ordinal]!,column,config) }
      catch {
        issueCount++
        if (issues.length < LIMITS.issues) issues.push({row:index+1,line:row.line,column:column.name,code:'invalid_'+column.type,message:`Valeur incompatible avec le type ${column.type} et les conventions choisies.`})
      }
    })
    rows.push({rowNumber:index+1,sourceLine:row.line,values,original})
    if(index%1000===0) await setImmediate()
  }
  return { report:{valid:issueCount===0,issueCount,issues,truncated:issueCount>issues.length,rowCount:parsed.rows.length,columnCount:parsed.headers.length}, rows }
}
export function reportCsv(report: Validation) {
  const safe = (value: unknown) => { const text = String(value ?? ''); return '"'+(/^[=+\-@\t\r]/.test(text) ? "'"+text : text).replaceAll('"','""')+'"' }
  return '\uFEFF'+[['ligne_donnee','ligne_source','colonne','code','raison'],...report.issues.map(issue => [issue.row,issue.line,issue.column,issue.code,issue.message])].map(row => row.map(safe).join(',')).join('\r\n')+'\r\n'
}
