/** Application / review / project status labels for UI. */

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  submitted: '已提交',
  mentor_review: '导师审核中',
  community_review: '导师已通过 · 名额已预留（待社区）',
  committee_review: '名额已预留 · 待组委会终审',
  selected: '已中选',
  rejected: '未通过',
  withdrawn: '已放弃/取消',
  in_progress: '开发中',
  final_draft: '结项草稿',
  final_submitted: '结项已提交',
  mentor_final_review: '导师结项审核中',
  committee_final_review: '组委会结项审核中',
  final_rejected: '结项未通过',
  completed: '已结项',
}

const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  closed: '已关闭接取',
}

const NODE_LABELS: Record<string, string> = {
  none: '未进入审核',
  mentor: '导师审核',
  community: '社区审核',
  committee: '组委会审核',
  final: '结项审核',
}

const ACTOR_LABELS: Record<string, string> = {
  student: '学生',
  mentor: '导师',
  community_admin: '社区管理员',
  committee: '组委会',
  system: '系统',
}

const ACTION_LABELS: Record<string, string> = {
  submit: '提交申请',
  start_mentor_review: '进入导师审核',
  approve_mentor: '导师通过',
  approve_community: '社区通过',
  approve_committee: '组委会通过',
  approve: '通过',
  reject: '未通过',
  reject_final: '验收未通过',
  start_progress: '启动开发',
  submit_final: '提交验收',
  start_mentor_final: '进入导师结项审',
  approve_mentor_final: '导师结项通过',
  approve_committee_final: '组委会结项通过',
  withdraw: '学生放弃接取',
  cancel_assignment: '导师取消接取',
}

export function statusLabel(status?: string | null): string {
  if (!status) return '未知'
  return STATUS_LABELS[status] || status
}

export function projectStatusLabel(status?: string | null): string {
  if (!status) return '未知'
  return PROJECT_STATUS_LABELS[status] || statusLabel(status)
}

export function nodeLabel(node?: string | null): string {
  if (!node) return ''
  return NODE_LABELS[node] || node
}

export function actorRoleLabel(role?: string | null): string {
  if (!role) return ''
  return ACTOR_LABELS[role] || role
}

export function actionLabel(action?: string | null): string {
  if (!action) return ''
  return ACTION_LABELS[action] || action
}

export function statusTone(status?: string | null): string {
  if (!status) return 'slate'
  if (status.includes('reject') || status === 'withdrawn') return 'danger'
  if (['selected', 'completed', 'in_progress', 'published'].includes(status)) return 'green'
  if (status.includes('review') || status.includes('submitted')) return 'warn'
  return 'slate'
}

/** 友好时间：2026-09-20 18:32 */
export function formatDateTime(raw?: string | null): string {
  if (!raw) return ''
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) {
    return String(raw).replace('T', ' ').slice(0, 19)
  }
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
