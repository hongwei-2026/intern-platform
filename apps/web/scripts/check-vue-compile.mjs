#!/usr/bin/env node
/**
 * 用 @vue/compiler-sfc 编译全部 .vue，拦住 Vite 500（模板解析失败）。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '../src')

/** @type {string[]} */
const errors = []

function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    const st = fs.statSync(full)
    if (st.isDirectory()) walk(full)
    else if (name.endsWith('.vue')) compileVue(full)
  }
}

function compileVue(file) {
  const rel = path.relative(srcRoot, file).replace(/\\/g, '/')
  const source = fs.readFileSync(file, 'utf8')
  const { descriptor, errors: parseErrors } = parse(source, { filename: file })
  if (parseErrors?.length) {
    for (const e of parseErrors) {
      errors.push(`${rel}: parse: ${e.message || e}`)
    }
    return
  }

  if (descriptor.script || descriptor.scriptSetup) {
    try {
      compileScript(descriptor, { id: rel })
    } catch (e) {
      errors.push(`${rel}: script: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  if (descriptor.template) {
    const result = compileTemplate({
      id: rel,
      filename: file,
      source: descriptor.template.content,
      scoped: descriptor.styles.some((s) => s.scoped),
      compilerOptions: { mode: 'module' },
    })
    if (result.errors?.length) {
      for (const e of result.errors) {
        errors.push(`${rel}: template: ${typeof e === 'string' ? e : e.message || e}`)
      }
    }
  }
}

walk(srcRoot)

if (errors.length) {
  console.error('Vue SFC compile FAILED:\n')
  for (const e of errors) console.error(`  ${e}`)
  process.exit(1)
}

console.log('Vue SFC compile OK')
