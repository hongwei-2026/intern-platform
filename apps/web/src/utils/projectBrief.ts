/** Parse OSPP-style structured brief stored in project.description (JSON) or fall back. */

export type BriefSection = {
  title: string
  body?: string
  items?: string[]
}

export type ProjectBrief = {
  lang?: string
  domains?: string[]
  languages?: string[]
  license?: string
  cycle?: string
  arch?: string
  mentor_name?: string
  mentor_email?: string
  heat?: number
  sections?: BriefSection[]
  outputs?: string[]
  tech_requirements?: string[]
}

export function parseStack(raw?: string | null): string[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    if (Array.isArray(v)) return v.map(String).filter(Boolean)
  } catch {
    /* plain */
  }
  return raw
    .split(/[,，|/]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export function parseBrief(description?: string | null, summary?: string | null): ProjectBrief {
  if (description) {
    const trimmed = description.trim()
    if (trimmed.startsWith('{')) {
      try {
        const data = JSON.parse(trimmed) as ProjectBrief
        if (data && (data.sections || data.outputs || data.tech_requirements)) {
          return data
        }
      } catch {
        /* fall through */
      }
    }
  }

  const text = description?.trim() || summary?.trim() || ''
  return {
    sections: text
      ? [{ title: '背景介绍', body: text }]
      : [{ title: '背景介绍', body: '导师尚未填写详细任务说明。' }],
    outputs: ['完成课题约定的代码 / 文档产出，并以 PR/MR 形式提交', '提交结项报告，说明目标、工作与结果'],
    tech_requirements: ['具备相关技术栈基础，能独立完成开发与联调', '熟悉 Git 协作与 Code Review 流程'],
  }
}

export function difficultyLabel(raw?: string | null): string {
  const map: Record<string, string> = {
    easy: '基础',
    medium: '进阶',
    hard: '挑战',
    basic: '基础',
    advanced: '进阶',
  }
  if (!raw) return '未标注'
  return map[raw.toLowerCase()] || raw
}

/** 技术栈 / 领域标签中文化（项目名本身可保留英文） */
const STACK_ZH: Record<string, string> = {
  c: 'C语言',
  'c++': 'C++',
  'c#': 'C#',
  python: 'Python',
  java: 'Java',
  javascript: 'JavaScript',
  typescript: 'TypeScript',
  bash: 'Shell脚本',
  shell: 'Shell脚本',
  markdown: 'Markdown',
  git: 'Git',
  docker: 'Docker',
  pytorch: 'PyTorch',
  linux: 'Linux',
  'risc-v': 'RISC-V',
  compiler: '编译器',
  'deep learning': '深度学习',
  ai: '人工智能',
  rtos: '实时操作系统',
  kvm: '虚拟化',
  database: '数据库',
  embedded: '嵌入式',
  docs: '文档',
  devops: '运维开发',
  操作系统: '操作系统',
  编译器: '编译器',
  深度学习: '深度学习',
  人工智能: '人工智能',
  数据库: '数据库',
  嵌入式: '嵌入式',
  文档: '文档',
  镜像: '镜像',
  实时操作系统: '实时操作系统',
}

export function stackLabel(raw: string): string {
  const s = String(raw || '').trim()
  if (!s) return ''
  return STACK_ZH[s.toLowerCase()] || STACK_ZH[s] || s
}

export function stackLabels(items: string[]): string[] {
  return items.map(stackLabel).filter(Boolean)
}

export function langLabel(raw?: string | null): string {
  if (!raw || raw === '中文') return '中文'
  if (raw.includes('英') || raw.toLowerCase().includes('en')) return '中文与英文'
  return raw
}

export function projectCode(id: number): string {
  return `HUST${String(id).padStart(5, '0')}`
}
