#!/usr/bin/env node
/**
 * 前端结构守卫：公开主页 / 组织台职责分离（踩坑：一页塞编辑+邀请+分配显得拥挤）。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '../src')

/** @type {string[]} */
const errors = []

function read(rel) {
  return fs.readFileSync(path.join(srcRoot, rel), 'utf8')
}

function mustInclude(rel, needles, label) {
  const src = read(rel)
  for (const n of needles) {
    if (!src.includes(n)) errors.push(`${rel}: 缺少「${n}」（${label}）`)
  }
}

function mustNotMatch(rel, patterns, label) {
  const src = read(rel)
  for (const re of patterns) {
    if (re.test(src)) errors.push(`${rel}: 命中禁止模式 ${re}（${label}）`)
  }
}

// 公开组织主页：OSPP 风格信息页，禁止管理动作与邀请码
mustInclude(
  'views/CommunityDetailView.vue',
  ['官网主页', 'org-profile', '社区任务'],
  '公开主页应有 Logo/官网/任务区',
)
mustNotMatch(
  'views/CommunityDetailView.vue',
  [
    /invite_code/,
    /邀请码/,
    /@click=["']editingHome/,
    />\s*编辑\s*</,
  ],
  '公开主页不得出现编辑/邀请码',
)

// 组织工作台：Tab 拆分，避免并排三卡
mustInclude(
  'views/org/OrgPortalView.vue',
  ["tab === 'home'", "tab === 'mentors'", "tab === 'projects'", '查看公开主页'],
  '组织台须 Tab 分区且可跳转公开主页',
)
mustNotMatch(
  'views/org/OrgPortalView.vue',
  [/维护社区主页\s*[·・]\s*邀请导师/, /grid-template-columns:\s*1fr\s+1fr\s+1fr/],
  '禁止回到「三职责并排」拥挤布局',
)

if (errors.length) {
  console.error('Vue structure guard FAILED:\n')
  for (const e of errors) console.error(`  ${e}`)
  process.exit(1)
}

console.log('Vue structure guard OK')
