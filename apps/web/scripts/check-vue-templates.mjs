#!/usr/bin/env node
/**
 * 禁止在 Vue <template> 中写 TypeScript 语法。
 * 踩坑：`(e.target as HTMLSelectElement)` / `myCommunity!` 会让
 * @vue/compiler-dom 解析失败 → Vite 对 .vue 返回 500。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '../src')

/** @type {{file: string, line: number, text: string, reason: string}[]} */
const findings = []

function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    const st = fs.statSync(full)
    if (st.isDirectory()) walk(full)
    else if (name.endsWith('.vue')) checkVue(full)
  }
}

function extractTemplate(source) {
  const m = source.match(/<template\b[^>]*>([\s\S]*?)<\/template>/i)
  return m ? m[1] : ''
}

function checkVue(file) {
  const source = fs.readFileSync(file, 'utf8')
  const tpl = extractTemplate(source)
  if (!tpl) return
  const rel = path.relative(srcRoot, file).replace(/\\/g, '/')
  const lines = tpl.split(/\r?\n/)

  const rules = [
    {
      re: /\bas\s+[A-Za-z_$][\w$.|<>[\]]*/,
      reason: 'template 禁止 TypeScript `as` 类型断言，请放到 <script> 处理',
    },
    {
      re: /\w!\./,
      reason: 'template 禁止非空断言 `!.`，请用可选链或 script 包装',
    },
    {
      re: /\w!\s*[\)\}\],]/,
      reason: 'template 禁止非空断言 `!`，请用可选链或 script 包装',
    },
    {
      re: /\$event\.target\s+as\b/,
      reason: '禁止在 @change 等处对 $event 做 as 断言',
    },
  ]

  lines.forEach((text, idx) => {
    // 跳过纯注释行
    if (/^\s*<!--/.test(text)) return
    for (const rule of rules) {
      if (rule.re.test(text)) {
        findings.push({ file: rel, line: idx + 1, text: text.trim(), reason: rule.reason })
        break
      }
    }
  })
}

walk(srcRoot)

if (findings.length) {
  console.error('Vue template TypeScript guard FAILED:\n')
  for (const f of findings) {
    console.error(`  src/${f.file}:${f.line}`)
    console.error(`    ${f.reason}`)
    console.error(`    > ${f.text}\n`)
  }
  process.exit(1)
}

console.log('Vue template TypeScript guard OK')
