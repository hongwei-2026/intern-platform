/** Application / review / project status labels for UI. */

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  submitted: '已提交',
  mentor_review: '导师审核中',
  community_review: '导师已通过 · 名额已预留（待社区审核）',
  committee_review: '社区已通过 · 组委会接收中',
  selected: '已中选',
  rejected: '未通过',
  withdrawn: '已放弃/取消',
  in_progress: '开发中',
  final_draft: '结项草稿',
  final_submitted: '结项已提交',
  mentor_final_review: '导师结项审核中',
  community_final_review: '验收已通过 · 待社区报送',
  committee_final_review: '组委会已接收结项',
  final_rejected: '结项未通过',
  completed: '已结项',
}

const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  closed: '已关闭接取',
  offline: '已下架',
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
  submit_community_final: '社区报送结项',
  approve_committee_final: '组委会自动接收结项',
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

/** 列表上的阶段说明。结项状态不使用「社区审核」这种申请阶段节点名。 */
const STAGE_BY_STATUS: Record<string, string> = {
  community_final_review: '结项验收',
  committee_final_review: '结项验收',
  mentor_final_review: '验收中',
  final_submitted: '验收中',
  final_rejected: '验收未通过',
  completed: '已结项',
  in_progress: '任务开发中',
  community_review: '名额已预留，待社区审核',
  committee_review: '社区已通过，组委会已接收',
}

export function stageLabel(status?: string | null, node?: string | null): string {
  if (status && STAGE_BY_STATUS[status]) return STAGE_BY_STATUS[status]
  return nodeLabel(node) || statusLabel(status)
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
  if (['selected', 'completed', 'in_progress', 'published', 'community_final_review'].includes(status)) return 'green'
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
